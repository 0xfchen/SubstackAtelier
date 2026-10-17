/**
 * three-graph.ts
 *
 * 3D Constellation Knowledge Graph View orchestrator for SubstackAtelier.
 * Renders an interactive 3D universe of articles, topic clusters, and publication hubs.
 * Integrates force-directed physics relaxation, chronological universe expansion scrubbing,
 * reading status synchronization, and detailed cosmic inspection.
 */

import * as THREE from 'three';
import {
  fetchReadingState,
  getReadingStatus,
  READING_STATUS_CHANGE_EVENT,
} from './reading-tracker';
import {
  getNodeReadingColor,
  getNodeTopicColor,
} from '../utils/graph-colors';
import { GRAPH_SCENE_COLORS } from '../utils/colors';
import type {
  GraphData,
  GraphLink,
  GraphNode,
  SimNode,
  ActiveLink,
} from './graph/types';
import {
  createGraphGeometries,
  createGraphMaterials,
} from './graph/mesh-factory';
import { GraphPhysicsEngine } from './graph/physics';
import { TimelineManager } from './graph/timeline';
import { setupGraphScene } from './graph/scene-setup';
import { setupGraphInteraction } from './graph/interaction';
import {
  setupGraphFilterControls,
  matchesNodeCategory,
  matchesNodeSearch,
} from './graph/filters';
import { hideGraphInspector } from './graph/inspector';
import { GRAPH_SELECTORS, queryRequiredElement } from './graph/selectors';
import { createSceneLifecycle } from './shared/scene-lifecycle';

export type { GraphData, GraphLink, GraphNode, SimNode };

function isDarkTheme(): boolean {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

export function initThreeGraph(): (() => void) | null {
  const containerElement = document.querySelector<HTMLElement>(
    GRAPH_SELECTORS.container
  );
  if (!containerElement) return null;

  const dataPayloadElement =
    document.getElementById('graph-data-payload') ||
    document.getElementById('graph-data');
  if (!dataPayloadElement || !dataPayloadElement.textContent) return null;

  let graphData: GraphData;
  try {
    graphData = JSON.parse(dataPayloadElement.textContent);
  } catch (error) {
    console.error('Failed to parse graph JSON data:', error);
    return null;
  }

  const canvasElement = containerElement.querySelector<HTMLCanvasElement>(
    GRAPH_SELECTORS.canvas
  );
  if (!canvasElement) return null;

  const container = containerElement;
  const canvas = canvasElement;

  // 1. Scene, Camera, WebGL Renderer, OrbitControls, and Studio Lighting
  const sceneSetup = setupGraphScene(container, canvas, isDarkTheme());
  const { scene, camera, renderer, controls } = sceneSetup;

  let targetCameraPosition: THREE.Vector3 | null = null;
  let targetControlsTarget: THREE.Vector3 | null = null;

  // 2. Geometries & Materials
  const rawNodes = graphData.nodes || [];
  const geometries = createGraphGeometries();
  const materials = createGraphMaterials(isDarkTheme());

  // 3. Node Distribution & Mesh Instantiation
  const nodeMap = new Map<string, number>();
  const nodes: SimNode[] = rawNodes.map((rawNode, nodeIndex) => {
    nodeMap.set(rawNode.id, nodeIndex);
    return {
      ...rawNode,
      id: rawNode.id,
      name: rawNode.name,
      type: rawNode.type,
      readingStatus:
        rawNode.type === 'post'
          ? getReadingStatus(rawNode.postId || rawNode.id.replace(/^post:/, '')) ||
            rawNode.readingStatus ||
            'unread'
          : undefined,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
    };
  });

  const nodeMeshes: THREE.Mesh[] = [];
  const nodeCount = nodes.length;
  const initialSphereRadius = Math.min(
    140,
    Math.max(60, Math.cbrt(nodeCount) * 16)
  );
  const goldenRatioAngle = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < nodeCount; i++) {
    const node = nodes[i];
    const normalizedY = 1 - (i / (nodeCount - 1 || 1)) * 2;
    const horizontalRadius = Math.sqrt(
      Math.max(0, 1 - normalizedY * normalizedY)
    );
    const thetaAngle = goldenRatioAngle * i;

    node.x = Math.cos(thetaAngle) * horizontalRadius * initialSphereRadius;
    node.y = normalizedY * initialSphereRadius;
    node.z = Math.sin(thetaAngle) * horizontalRadius * initialSphereRadius;

    const baseColor = getNodeTopicColor(node, isDarkTheme());
    const nodeGeometry = geometries.getNodeGeo(node, isDarkTheme());
    const nodeMaterial = new THREE.MeshStandardMaterial({
      color: baseColor,
      roughness: isDarkTheme() ? 0.25 : 0.35,
      metalness: isDarkTheme() ? 0.1 : 0.02,
      emissive: isDarkTheme() ? baseColor : 0x000000,
      emissiveIntensity: isDarkTheme() ? 0.35 : 0.0,
      transparent: true,
      opacity: isDarkTheme() ? 0.94 : 0.96,
    });

    const mesh = new THREE.Mesh(nodeGeometry, nodeMaterial);
    mesh.position.set(node.x, node.y, node.z);

    const baseScaleMultiplier =
      node.type === 'author' ? 1.5 : node.type === 'tag' ? 1.15 : 0.95;
    mesh.scale.set(
      baseScaleMultiplier,
      baseScaleMultiplier,
      baseScaleMultiplier
    );

    mesh.userData = {
      index: i,
      node,
      baseScale: baseScaleMultiplier,
      originalColor: baseColor,
    };

    nodeMeshes.push(mesh);
    scene.add(mesh);
  }

  // 4. Edges & Link Geometry
  const rawLinks = graphData.links || [];
  const validLinks: ActiveLink[] = [];

  for (const rawLink of rawLinks) {
    const sourceNodeIndex = nodeMap.get(rawLink.source);
    const targetNodeIndex = nodeMap.get(rawLink.target);
    if (sourceNodeIndex !== undefined && targetNodeIndex !== undefined) {
      validLinks.push({
        sourceIdx: sourceNodeIndex,
        targetIdx: targetNodeIndex,
        weight: rawLink.weight || 1,
        type: rawLink.type || 'tag',
      });
    }
  }

  const linkCount = validLinks.length;
  const linkPositionArray = new Float32Array(linkCount * 6);
  const linkGeometry = new THREE.BufferGeometry();
  linkGeometry.setAttribute(
    'position',
    new THREE.BufferAttribute(linkPositionArray, 3)
  );

  const linkLines = new THREE.LineSegments(linkGeometry, materials.linkMaterial);
  scene.add(linkLines);

  const maxActiveLinks = 80;
  const activeLinkGeometry = new THREE.BufferGeometry();
  activeLinkGeometry.setAttribute(
    'position',
    new THREE.BufferAttribute(new Float32Array(maxActiveLinks * 6), 3)
  );
  const activeLinkLines = new THREE.LineSegments(
    activeLinkGeometry,
    materials.activeLinkMaterial
  );
  activeLinkLines.visible = false;
  scene.add(activeLinkLines);

  // 5. Starfield Dust (Cosmic Depth in Dark Mode)
  const starParticleCount = 600;
  const starParticleGeometry = new THREE.BufferGeometry();
  const starPositionArray = new Float32Array(starParticleCount * 3);
  for (let i = 0; i < starParticleCount * 3; i++) {
    starPositionArray[i] = (Math.random() - 0.5) * 800;
  }
  starParticleGeometry.setAttribute(
    'position',
    new THREE.BufferAttribute(starPositionArray, 3)
  );
  const starParticleMaterial = new THREE.PointsMaterial({
    color: GRAPH_SCENE_COLORS.starMatDark,
    size: 1.2,
    transparent: true,
    opacity: 0.35,
  });
  const starsParticles = new THREE.Points(
    starParticleGeometry,
    starParticleMaterial
  );
  starsParticles.visible = isDarkTheme();
  scene.add(starsParticles);

  // 6. Physics Simulation Engine
  let showAuthorHubs = true;
  const physicsEngine = new GraphPhysicsEngine(
    nodes,
    validLinks,
    nodeMeshes,
    linkGeometry,
    activeLinkGeometry,
    { showAuthorHubs }
  );
  physicsEngine.prewarm(30);

  // 7. Timeline Manager
  const timelineManager = new TimelineManager(nodes);

  // 8. Visibility Filter Evaluator
  let activeColorMode: 'topic' | 'reading' = 'topic';

  const applyVisibility = () => {
    const searchFilterQuery = filterControls.getSearchQuery();
    const activeCategoryCriteria = filterControls.getActiveFilter();
    const isTimelinePresent = timelineManager.isPresent();
    const chronologicalCutoffTime = timelineManager.getCutoffTime();
    const isDark = isDarkTheme();

    let visiblePostCount = 0;
    let totalPostCount = 0;

    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const nodeMesh = nodeMeshes[i];
      const standardMaterial = nodeMesh.material as THREE.MeshStandardMaterial;
      const baseScaleMultiplier =
        (nodeMesh.userData.baseScale as number) || 1.0;

      if (node.type === 'post') totalPostCount++;

      const nodeBirthTimestamp = timelineManager.nodeBirthTimestamps[i];
      const isNodeBorn =
        isTimelinePresent || nodeBirthTimestamp <= chronologicalCutoffTime;

      if (node.type === 'post' && isNodeBorn) {
        visiblePostCount++;
      }

      if (!isNodeBorn) {
        timelineManager.wasBorn[i] = 0;
        timelineManager.activePopAnimations.delete(i);
        nodeMesh.visible = false;
        nodeMesh.scale.set(0, 0, 0);
        continue;
      }

      if (timelineManager.wasBorn[i] === 0) {
        timelineManager.wasBorn[i] = 1;
        timelineManager.activePopAnimations.set(i, {
          startTime: performance.now(),
          duration: 480,
        });
      }
      nodeMesh.visible = true;

      const matchesCategory = matchesNodeCategory(node, activeCategoryCriteria);
      const matchesSearch = matchesNodeSearch(node, searchFilterQuery);

      if (!timelineManager.activePopAnimations.has(i)) {
        if (matchesCategory && matchesSearch) {
          standardMaterial.opacity = isDark ? 0.94 : 0.96;
          nodeMesh.scale.set(
            baseScaleMultiplier,
            baseScaleMultiplier,
            baseScaleMultiplier
          );
        } else {
          standardMaterial.opacity = isDark ? 0.05 : 0.08;
          const dimmedScale = baseScaleMultiplier * 0.55;
          nodeMesh.scale.set(dimmedScale, dimmedScale, dimmedScale);
        }
      }
    }

    physicsEngine.updateLinkEndpoints();
    timelineManager.updateHUD(container, visiblePostCount, totalPostCount);
  };

  // 9. Interaction Manager (Raycasting, Hover, Highlighting, Tooltip)
  const interactionManager = setupGraphInteraction({
    containerElement: container,
    canvasElement: canvas,
    camera,
    controls,
    nodes,
    nodeMeshes,
    validLinks,
    activeLinkLines,
    activeLinkGeometry,
    linkMaterial: materials.linkMaterial,
    maxActiveLinks,
    isDarkTheme,
    getShowAuthorHubs: () => showAuthorHubs,
    onResetHighlights: () => {
      applyVisibility();
    },
    onCameraFocusRequested: (
      targetCameraPosVector,
      targetControlsTargetVector
    ) => {
      targetCameraPosition = targetCameraPosVector;
      targetControlsTarget = targetControlsTargetVector;
    },
  });

  // 10. Filter & Search Controls
  const filterControls = setupGraphFilterControls(container, () => {
    applyVisibility();
    physicsEngine.reheat(0.15);
  });

  // 11. Timeline Controls Wiring
  const timelineSliderElement = queryRequiredElement<HTMLInputElement>(
    container,
    GRAPH_SELECTORS.timelineSlider,
    'Timeline Slider'
  );
  const timelinePlayButtonElement = queryRequiredElement<HTMLButtonElement>(
    container,
    GRAPH_SELECTORS.timelinePlayButton,
    'Timeline Play Button'
  );
  const timelineSpeedButtonElement = queryRequiredElement<HTMLButtonElement>(
    container,
    GRAPH_SELECTORS.timelineSpeedButton,
    'Timeline Speed Button'
  );
  const timelinePresentButtonElement = queryRequiredElement<HTMLButtonElement>(
    container,
    GRAPH_SELECTORS.timelinePresentButton,
    'Timeline Present Button'
  );

  const handleTimelineSliderInput = () => {
    timelineManager.setPlaying(container, false);
    if (timelineSliderElement) {
      const sliderIntegerVal = parseInt(timelineSliderElement.value, 10);
      timelineManager.timelineFraction = Math.max(
        0,
        Math.min(1, sliderIntegerVal / 1000)
      );
      applyVisibility();
    }
  };
  timelineSliderElement?.addEventListener('input', handleTimelineSliderInput);

  const handleTimelinePlayToggle = () => {
    if (timelineManager.isPlaying) {
      timelineManager.setPlaying(container, false);
    } else {
      if (timelineManager.timelineFraction >= 0.999) {
        timelineManager.timelineFraction = 0.0;
        if (timelineSliderElement) timelineSliderElement.value = '0';
      }
      timelineManager.setPlaying(container, true);
      timelineManager.lastTimelineTime = performance.now();
    }
  };
  timelinePlayButtonElement?.addEventListener(
    'click',
    handleTimelinePlayToggle
  );

  const handleTimelineSpeedClick = () => {
    timelineManager.cycleSpeed(container);
  };
  timelineSpeedButtonElement?.addEventListener(
    'click',
    handleTimelineSpeedClick
  );

  const handleTimelinePresentClick = () => {
    timelineManager.setPlaying(container, false);
    timelineManager.timelineFraction = 1.0;
    if (timelineSliderElement) timelineSliderElement.value = '1000';
    applyVisibility();
  };
  timelinePresentButtonElement?.addEventListener(
    'click',
    handleTimelinePresentClick
  );

  // 12. Mode & Camera Action Buttons
  const colorModeButtonElement = queryRequiredElement<HTMLButtonElement>(
    container,
    GRAPH_SELECTORS.colorModeButton,
    'Color Mode Button'
  );
  const colorModeLabelElement = container.querySelector<HTMLElement>(
    GRAPH_SELECTORS.colorModeLabel
  );
  const legendTopicsGroupElement = container.querySelector<HTMLElement>(
    GRAPH_SELECTORS.legendTopics
  );
  const legendReadingGroupElement = container.querySelector<HTMLElement>(
    GRAPH_SELECTORS.legendReading
  );
  const filterGroupTopicsElement = container.querySelector<HTMLElement>(
    GRAPH_SELECTORS.filterGroupTopics
  );
  const filterGroupReadingElement = container.querySelector<HTMLElement>(
    GRAPH_SELECTORS.filterGroupReading
  );

  const handleColorModeToggle = () => {
    activeColorMode = activeColorMode === 'topic' ? 'reading' : 'topic';
    const isReading = activeColorMode === 'reading';
    const isDark = isDarkTheme();

    if (colorModeButtonElement) {
      colorModeButtonElement.classList.toggle('active', isReading);
    }
    if (colorModeLabelElement) {
      colorModeLabelElement.textContent = isReading
        ? 'Color: Reading Status'
        : 'Color: Topics';
    }

    if (legendTopicsGroupElement && legendReadingGroupElement) {
      legendTopicsGroupElement.classList.toggle('hidden', isReading);
      legendReadingGroupElement.classList.toggle('hidden', !isReading);
    }

    filterGroupTopicsElement?.classList.toggle('hidden', isReading);
    filterGroupReadingElement?.classList.toggle('hidden', !isReading);

    const activeFilterGroup = isReading
      ? filterGroupReadingElement
      : filterGroupTopicsElement;
    const allFilterButton = activeFilterGroup?.querySelector<HTMLButtonElement>(
      '[data-filter="all"], [data-graph-filter="all"]'
    );
    if (allFilterButton) {
      allFilterButton.click();
    }

    nodeMeshes.forEach((meshItem) => {
      const node = meshItem.userData.node as GraphNode;
      const targetColor =
        activeColorMode === 'topic'
          ? getNodeTopicColor(node, isDark)
          : getNodeReadingColor(node, isDark);
      meshItem.userData.originalColor = targetColor;
      const standardMaterial = meshItem.material as THREE.MeshStandardMaterial;
      standardMaterial.color.setHex(targetColor);
      standardMaterial.emissive.setHex(isDark ? targetColor : 0x000000);
      standardMaterial.emissiveIntensity = isDark ? 0.35 : 0.0;
    });
  };
  colorModeButtonElement?.addEventListener('click', handleColorModeToggle);

  const resetCameraButtonElement = queryRequiredElement<HTMLButtonElement>(
    container,
    GRAPH_SELECTORS.resetCameraButton,
    'Reset Camera Button'
  );
  const handleResetCameraClick = () => {
    targetCameraPosition = sceneSetup.defaultCameraPosition.clone();
    targetControlsTarget = new THREE.Vector3(0, 0, 0);
    controls.autoRotate = true;
    interactionManager.resetMeshHighlights();
    hideGraphInspector(container);
  };
  resetCameraButtonElement?.addEventListener('click', handleResetCameraClick);

  // 13. Theme Synchronization
  const updateTheme = (isDark: boolean) => {
    sceneSetup.updateLightingForTheme(isDark);
    starsParticles.visible = isDark;

    materials.linkMaterial.color.setHex(
      isDark ? GRAPH_SCENE_COLORS.linksDark : GRAPH_SCENE_COLORS.linksLight
    );
    materials.linkMaterial.opacity =
      interactionManager.getCurrentHighlightedIndex() !== null
        ? isDark
          ? 0.015
          : 0.04
        : isDark
          ? 0.1
          : 0.22;

    materials.activeLinkMaterial.color.setHex(
      isDark
        ? GRAPH_SCENE_COLORS.activeLinkDark
        : GRAPH_SCENE_COLORS.activeLinkLight
    );

    nodeMeshes.forEach((meshItem) => {
      const node = meshItem.userData.node as GraphNode;
      const targetColor =
        activeColorMode === 'topic'
          ? getNodeTopicColor(node, isDark)
          : getNodeReadingColor(node, isDark);
      meshItem.userData.originalColor = targetColor;
      meshItem.geometry = geometries.getNodeGeo(node, isDark);
      const standardMaterial = meshItem.material as THREE.MeshStandardMaterial;
      standardMaterial.color.setHex(targetColor);
      standardMaterial.roughness = isDark ? 0.25 : 0.35;
      standardMaterial.metalness = isDark ? 0.1 : 0.02;
      standardMaterial.emissive.setHex(isDark ? targetColor : 0x000000);
      standardMaterial.emissiveIntensity = isDark ? 0.35 : 0.0;
      standardMaterial.opacity = isDark ? 0.94 : 0.96;
    });

    const timelineTitleElement = container.querySelector<HTMLElement>(
      GRAPH_SELECTORS.timelineTitle
    );
    if (timelineTitleElement) {
      timelineTitleElement.textContent = isDark
        ? 'Universe Expansion'
        : 'Knowledge Evolution';
    }

    const legendAuthorElement = container.querySelector<HTMLElement>(
      GRAPH_SELECTORS.legendLabelAuthor
    );
    if (legendAuthorElement) {
      legendAuthorElement.textContent = isDark
        ? 'Publication (Planet)'
        : 'Publication (Core Hub)';
    }

    const legendTagElement = container.querySelector<HTMLElement>(
      GRAPH_SELECTORS.legendLabelTag
    );
    if (legendTagElement) {
      legendTagElement.textContent = isDark
        ? 'Topic (Star)'
        : 'Topic (Subject Diamond)';
    }

    const legendPostElement = container.querySelector<HTMLElement>(
      GRAPH_SELECTORS.legendLabelPost
    );
    if (legendPostElement) {
      legendPostElement.textContent = isDark
        ? 'Article (Asteroid)'
        : 'Article (Document Folio)';
    }

    if (timelinePresentButtonElement) {
      timelinePresentButtonElement.title = isDark
        ? 'Reset to Present (Full Cosmos)'
        : 'Reset to Full Network';
    }
  };

  // 14. Reading State Synchronization
  const syncReadingState = () => {
    nodeMeshes.forEach((meshItem) => {
      const node = meshItem.userData.node as GraphNode;
      if (node.type === 'post') {
        const postSlug = node.postId || node.id.replace(/^post:/, '');
        node.readingStatus = getReadingStatus(postSlug) || 'unread';
        if (activeColorMode === 'reading') {
          const statusColor = getNodeReadingColor(node, isDarkTheme());
          meshItem.userData.originalColor = statusColor;
          const standardMaterial =
            meshItem.material as THREE.MeshStandardMaterial;
          standardMaterial.color.setHex(statusColor);
          standardMaterial.emissive.setHex(
            isDarkTheme() ? statusColor : 0x000000
          );
        }
      }
    });
    applyVisibility();
  };

  const handleReadingStatusChangedEvent = () => {
    syncReadingState();
  };
  window.addEventListener(
    READING_STATUS_CHANGE_EVENT,
    handleReadingStatusChangedEvent
  );

  fetchReadingState().then(() => syncReadingState()).catch(() => {});

  // 15. Shared Scene Lifecycle
  const lifecycleController = createSceneLifecycle({
    container,
    canvas,
    onAnimate: (timestamp) => {
      const timeDelta = Math.min(
        100,
        timestamp - timelineManager.lastTimelineTime
      );
      timelineManager.lastTimelineTime = timestamp;

      if (timelineManager.isPlaying) {
        const fullExpansionDuration = 18000 / timelineManager.playbackSpeed;
        timelineManager.timelineFraction += timeDelta / fullExpansionDuration;
        if (timelineManager.timelineFraction >= 1.0) {
          timelineManager.timelineFraction = 1.0;
          timelineManager.setPlaying(container, false);
        }
        if (timelineSliderElement) {
          timelineSliderElement.value = String(
            Math.round(timelineManager.timelineFraction * 1000)
          );
        }
        applyVisibility();
      }

      timelineManager.updatePopAnimations(
        timestamp,
        nodeMeshes,
        isDarkTheme()
      );

      physicsEngine.step(interactionManager.getCurrentHighlightedIndex());

      for (let i = 0; i < nodes.length; i++) {
        if (!nodeMeshes[i].visible) continue;
        const nodeType = nodes[i].type;
        if (nodeType === 'author') {
          nodeMeshes[i].rotation.y += 0.008;
          nodeMeshes[i].rotation.z += 0.002;
        } else if (nodeType === 'post') {
          nodeMeshes[i].rotation.x += 0.006;
          nodeMeshes[i].rotation.y += 0.009;
        } else if (nodeType === 'tag') {
          nodeMeshes[i].rotation.y += 0.004;
        }
      }

      if (targetCameraPosition && targetControlsTarget) {
        camera.position.lerp(targetCameraPosition, 0.08);
        controls.target.lerp(targetControlsTarget, 0.08);
        if (camera.position.distanceTo(targetCameraPosition) < 1.0) {
          targetCameraPosition = null;
          targetControlsTarget = null;
        }
      }

      controls.update();
      interactionManager.checkHover();
      renderer.render(scene, camera);
    },
    onResize: (viewportWidth, viewportHeight) => {
      sceneSetup.resizeViewport(viewportWidth, viewportHeight);
    },
    onThemeChange: (isDark) => {
      updateTheme(isDark);
    },
    onVisibilityChange: (isViewportVisible) => {
      if (isViewportVisible) {
        timelineManager.lastTimelineTime = performance.now();
      }
    },
    onTeardown: () => {
      timelineManager.setPlaying(container, false);

      try {
        delete (window as any).__threeGraph;
      } catch {
        (window as any).__threeGraph = undefined;
      }

      sceneSetup.dispose();
      interactionManager.dispose();
      filterControls.dispose();

      timelineSliderElement?.removeEventListener(
        'input',
        handleTimelineSliderInput
      );
      timelinePlayButtonElement?.removeEventListener(
        'click',
        handleTimelinePlayToggle
      );
      timelineSpeedButtonElement?.removeEventListener(
        'click',
        handleTimelineSpeedClick
      );
      timelinePresentButtonElement?.removeEventListener(
        'click',
        handleTimelinePresentClick
      );
      colorModeButtonElement?.removeEventListener(
        'click',
        handleColorModeToggle
      );
      resetCameraButtonElement?.removeEventListener(
        'click',
        handleResetCameraClick
      );
      window.removeEventListener(
        READING_STATUS_CHANGE_EVENT,
        handleReadingStatusChangedEvent
      );

      geometries.dispose();
      materials.dispose();
      linkGeometry.dispose();
      activeLinkGeometry.dispose();
      starParticleGeometry.dispose();
      starParticleMaterial.dispose();
    },
  });

  applyVisibility();
  lifecycleController.start();

  // 16. Window Scripting API for Automated Testing
  (window as any).__threeGraph = {
    camera,
    controls,
    scene,
    nodes,
    nodeMeshes,
    timeline: timelineManager,
    physics: physicsEngine,
    setTimelineFraction: (fractionRatio: number) => {
      timelineManager.setPlaying(container, false);
      timelineManager.timelineFraction = Math.max(0, Math.min(1, fractionRatio));
      if (timelineSliderElement) {
        timelineSliderElement.value = String(
          Math.round(timelineManager.timelineFraction * 1000)
        );
      }
      applyVisibility();
    },
    playTimeline: () => {
      if (timelineManager.timelineFraction >= 0.999) {
        timelineManager.timelineFraction = 0.0;
      }
      timelineManager.setPlaying(container, true);
      timelineManager.lastTimelineTime = performance.now();
    },
    pauseTimeline: () => {
      timelineManager.setPlaying(container, false);
    },
    focusNode: (targetIdentifier: string) => {
      const matchedNodeIndex = nodes.findIndex(
        (nodeItem) =>
          nodeItem.id.toLowerCase() === targetIdentifier.toLowerCase() ||
          nodeItem.name.toLowerCase() === targetIdentifier.toLowerCase() ||
          (nodeItem.author &&
            nodeItem.author.toLowerCase() === targetIdentifier.toLowerCase())
      );
      if (matchedNodeIndex !== -1) {
        interactionManager.selectNodeByIndex(matchedNodeIndex);
      }
    },
  };

  return () => {
    lifecycleController.teardown();
  };
}

let activeThreeGraphTeardown: (() => void) | null = null;

/**
 * Mounts the 3D Force-Directed Knowledge Graph scene, integrating with Astro lifecycle events.
 */
export function mountThreeGraphScene(): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  const setupScene = () => {
    if (typeof activeThreeGraphTeardown === 'function') {
      activeThreeGraphTeardown();
      activeThreeGraphTeardown = null;
    }
    activeThreeGraphTeardown = initThreeGraph();
  };

  document.addEventListener('astro:page-load', setupScene);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupScene, { once: true });
  } else if (!activeThreeGraphTeardown) {
    setupScene();
  }
}
