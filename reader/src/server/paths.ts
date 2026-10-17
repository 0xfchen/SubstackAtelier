/**
 * paths.ts
 *
 * Deterministic server-side path utilities for SubstackAtelier reader.
 * Anchored to import.meta.url to ensure filesystem resolution is invariant to process.cwd()
 * regardless of whether commands run from repo root or the reader directory.
 */

import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Resolves an absolute filesystem path within the repository root's content directory.
 * Anchored to import.meta.url to guarantee deterministic resolution regardless of process.cwd().
 *
 * @param subpaths Relative file or directory path segments within content/
 * @returns Normalized absolute path to the target file or directory
 */
export function getContentPath(...subpaths: string[]): string {
  const contentRootUrl = new URL('../../../content/', import.meta.url);
  const contentDirectoryPath = fileURLToPath(contentRootUrl);
  return path.resolve(contentDirectoryPath, ...subpaths);
}

