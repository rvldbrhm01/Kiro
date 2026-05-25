#!/usr/bin/env node
/**
 * Standalone CLI for SeaDrop FCFS minting.
 *
 * Usage:
 *   npm run snipe -- --chain eth --collection 0xAddr --qty 1
 *   npm run snipe -- --chain base --collection 0xAddr --qty 2 \
 *                    --priority-fee 5 --max-fee 80
 *   npm run snipe -- --chain eth --collection 0xAddr --qty 1 --dry-run
 */
import * as dotenv from "dotenv";
import { runFcfsMint, SnipeOptions } from "../snipe/minter";

dotenv.config();

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  if (i < 0) return undefined;
  return process.argv[i + 1];
}

function flag(name: string): boolean {
  return process.argv.includes(`--${name}`);
}

function usage(): never {
  console.error(
    "Usage: npm run snipe -- \\\n" +
      "  --chain eth|base \\\n" +
      "  --collection 0xCollectionAddress \\\n" +
      "  --qty <number> \\\n" +
      "  [--priority-fee <gwei>] [--max-fee <gwei>] \\\n" +
      "  [--preflight <seconds>] [--dry-run]",
  );
  process.exit(1);
}

async function main(): Promise<void> {
  const chain = arg("chain");
  const collection = arg("collection");
  const qtyRaw = arg("qty");

  if (!chain || !collection || !qtyRaw) usage();

  const quantity = Number(qtyRaw);
  if (!Number.isInteger(quantity) || quantity < 1) {
    console.error("--qty must be a positive integer");
    process.exit(1);
  }

  const privateKey = process.env.MINTER_PRIVATE_KEY;
  if (!privateKey) {
    console.error(
      "MINTER_PRIVATE_KEY is not set.\n" +
        "Use a DEDICATED hot wallet — never your main wallet's key.",
    );
    process.exit(1);
  }

  const opts: SnipeOptions = {
    chain: chain!,
    collection: collection!,
    quantity,
    privateKey,
    priorityFeeGwei: arg("priority-fee") ? Number(arg("priority-fee")) : undefined,
    maxFeeGwei: arg("max-fee") ? Number(arg("max-fee")) : undefined,
    preflightSeconds: arg("preflight") ? Number(arg("preflight")) : undefined,
    dryRun: flag("dry-run"),
  };

  const result = await runFcfsMint(opts);
  console.log("\n=== Result ===");
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.status === "success" ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
