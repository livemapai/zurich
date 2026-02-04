/**
 * Upload GTFS transit data to Vercel Blob
 *
 * Run: pnpm tsx scripts/upload-gtfs-to-blob.ts
 * Requires: BLOB_READ_WRITE_TOKEN in .env.local
 *
 * This uploads large transit files to Vercel Blob storage instead of Git LFS.
 * URLs are stable (addRandomSuffix: false) so no config changes needed after re-upload.
 */

import { put } from "@vercel/blob";
import { readFileSync, statSync, existsSync } from "fs";
import { basename } from "path";

interface FileToUpload {
	localPath: string;
	blobPath: string;
	description: string;
}

const FILES_TO_UPLOAD: FileToUpload[] = [
	{
		localPath: "public/data/gtfs/gtfs-trips.bin",
		blobPath: "data/gtfs/gtfs-trips.bin",
		description: "Binary trip data (chunked loading)",
	},
	{
		localPath: "public/data/gtfs/gtfs-trips.manifest.json",
		blobPath: "data/gtfs/gtfs-trips.manifest.json",
		description: "Chunk manifest",
	},
	{
		localPath: "public/data/zurich-tram-trips.json",
		blobPath: "data/zurich-tram-trips.json",
		description: "JSON fallback (all trips)",
	},
	{
		localPath: "public/data/zurich-tram-trips-terrain.json",
		blobPath: "data/zurich-tram-trips-terrain.json",
		description: "Terrain-adjusted trips",
	},
];

function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function uploadFile(file: FileToUpload): Promise<string | null> {
	if (!existsSync(file.localPath)) {
		console.warn(`⚠️  Skipping ${file.localPath} (file not found)`);
		return null;
	}

	const stats = statSync(file.localPath);
	const content = readFileSync(file.localPath);

	console.log(
		`📤 Uploading ${basename(file.localPath)} (${formatBytes(stats.size)})...`
	);

	const blob = await put(file.blobPath, content, {
		access: "public",
		addRandomSuffix: false, // Stable URLs - no config changes needed on re-upload
	});

	console.log(`   ✅ ${blob.url}`);
	return blob.url;
}

async function main() {
	console.log("🚀 Uploading GTFS data to Vercel Blob\n");

	if (!process.env.BLOB_READ_WRITE_TOKEN) {
		console.error(
			"❌ BLOB_READ_WRITE_TOKEN not found in environment.\n" +
				"   Add it to .env.local or set it in your shell:\n" +
				"   export BLOB_READ_WRITE_TOKEN=vercel_blob_rw_...\n"
		);
		process.exit(1);
	}

	const results: { file: string; url: string }[] = [];

	for (const file of FILES_TO_UPLOAD) {
		try {
			const url = await uploadFile(file);
			if (url) {
				results.push({ file: file.blobPath, url });
			}
		} catch (error) {
			console.error(`❌ Failed to upload ${file.localPath}:`, error);
			process.exit(1);
		}
	}

	console.log("\n✨ Upload complete!\n");
	console.log("Update src/lib/config.ts data paths with these URLs:");
	console.log("─".repeat(60));
	for (const result of results) {
		console.log(`${result.file}:`);
		console.log(`  ${result.url}`);
	}
	console.log("─".repeat(60));
}

main();
