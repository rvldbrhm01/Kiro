import { ethers } from "ethers";
import { ChainConfig, getChain, getRpcUrl, getSeaDropAddress } from "../chains";
import { SEADROP_ABI, readPublicDrop, pickFeeRecipient } from "./seadrop";

export interface SnipeOptions {
  chain: string; // "eth" | "base"
  collection: string; // NFT contract address
  quantity: number;
  privateKey: string; // hot wallet private key
  maxFeeGwei?: number; // EIP-1559 cap
  priorityFeeGwei?: number; // EIP-1559 tip
  preflightSeconds?: number; // submit this many seconds before startTime (default 0)
  gasLimitPerMint?: bigint; // gas limit per quantity unit (default 250_000)
  dryRun?: boolean; // log everything but don't broadcast
}

export interface SnipeResult {
  status: "success" | "failed" | "skipped";
  reason?: string;
  txHash?: string;
  explorerUrl?: string;
  chain: string;
  wallet: string;
}

export type Logger = (msg: string) => void;

const DEFAULT_GAS_PER_MINT = 250_000n;

export async function runFcfsMint(
  opts: SnipeOptions,
  log: Logger = console.log,
): Promise<SnipeResult> {
  const cfg: ChainConfig = getChain(opts.chain);
  const provider = new ethers.JsonRpcProvider(getRpcUrl(cfg));
  const wallet = new ethers.Wallet(opts.privateKey, provider);
  const seaDropAddress = getSeaDropAddress(cfg);
  const seaDrop = new ethers.Contract(seaDropAddress, SEADROP_ABI, wallet);

  const baseResult = { chain: cfg.key, wallet: wallet.address };

  log(`Chain:      ${cfg.name} (id ${cfg.chainId})`);
  log(`Wallet:     ${wallet.address}`);
  log(`SeaDrop:    ${seaDropAddress}`);
  log(`Collection: ${opts.collection}`);
  log(`Quantity:   ${opts.quantity}`);

  // -- 1. Read drop config ------------------------------------------------
  const drop = await readPublicDrop(seaDrop, opts.collection);
  if (drop.startTime === 0 && drop.endTime === 0) {
    return { ...baseResult, status: "failed", reason: "No public drop configured for this collection." };
  }
  log(
    `Drop:       price=${ethers.formatEther(drop.mintPrice)} ETH, ` +
      `start=${new Date(drop.startTime * 1000).toISOString()}, ` +
      `end=${new Date(drop.endTime * 1000).toISOString()}, ` +
      `maxPerWallet=${drop.maxTotalMintableByWallet}, ` +
      `feeBps=${drop.feeBps}`,
  );

  const now = Math.floor(Date.now() / 1000);
  if (now > drop.endTime) {
    return { ...baseResult, status: "skipped", reason: "Mint window already ended." };
  }
  if (drop.maxTotalMintableByWallet > 0 && opts.quantity > drop.maxTotalMintableByWallet) {
    return {
      ...baseResult,
      status: "failed",
      reason: `Quantity ${opts.quantity} exceeds per-wallet limit ${drop.maxTotalMintableByWallet}.`,
    };
  }

  // -- 2. Resolve fee recipient ------------------------------------------
  const feeRecipient = await pickFeeRecipient(seaDrop, opts.collection);
  log(`FeeRecip:   ${feeRecipient}`);

  // -- 3. Compute value & calldata ---------------------------------------
  // For SeaDrop public mint, msg.value must equal mintPrice * quantity;
  // the protocol fee is split on-chain from that value.
  const value = drop.mintPrice * BigInt(opts.quantity);
  log(`Value:      ${ethers.formatEther(value)} ETH`);

  const calldata = new ethers.Interface(SEADROP_ABI).encodeFunctionData("mintPublic", [
    opts.collection,
    feeRecipient,
    ethers.ZeroAddress, // minterIfNotPayer = 0x0 means payer mints to self
    opts.quantity,
  ]);

  // -- 4. Wait until startTime (FCFS) ------------------------------------
  const preflight = opts.preflightSeconds ?? 0;
  const submitAt = drop.startTime - preflight;
  const waitMs = (submitAt - Math.floor(Date.now() / 1000)) * 1000;
  if (waitMs > 0) {
    log(`Waiting ${(waitMs / 1000).toFixed(1)}s until submit window…`);
    await sleep(waitMs);
  } else {
    log(`Mint already open — submitting immediately.`);
  }

  // -- 5. Build EIP-1559 tx ----------------------------------------------
  const feeData = await provider.getFeeData();
  const priorityFee = opts.priorityFeeGwei !== undefined
    ? ethers.parseUnits(opts.priorityFeeGwei.toString(), "gwei")
    : (feeData.maxPriorityFeePerGas ?? ethers.parseUnits("2", "gwei"));
  const maxFee = opts.maxFeeGwei !== undefined
    ? ethers.parseUnits(opts.maxFeeGwei.toString(), "gwei")
    : ((feeData.maxFeePerGas ?? ethers.parseUnits("50", "gwei")) * 2n);

  const gasPerMint = opts.gasLimitPerMint ?? DEFAULT_GAS_PER_MINT;
  const gasLimit = gasPerMint * BigInt(opts.quantity);
  const nonce = await provider.getTransactionCount(wallet.address, "pending");

  const txReq: ethers.TransactionRequest = {
    to: seaDropAddress,
    data: calldata,
    value,
    chainId: cfg.chainId,
    nonce,
    type: 2,
    maxFeePerGas: maxFee,
    maxPriorityFeePerGas: priorityFee,
    gasLimit,
  };

  log(
    `Submitting tx: priority=${ethers.formatUnits(priorityFee, "gwei")} gwei, ` +
      `maxFee=${ethers.formatUnits(maxFee, "gwei")} gwei, ` +
      `gasLimit=${gasLimit.toString()}, nonce=${nonce}`,
  );

  if (opts.dryRun) {
    return { ...baseResult, status: "skipped", reason: "dry-run (no broadcast)" };
  }

  // -- 6. Broadcast & wait for receipt -----------------------------------
  try {
    const txResponse = await wallet.sendTransaction(txReq);
    const explorerUrl = `${cfg.blockExplorer}/tx/${txResponse.hash}`;
    log(`Sent: ${explorerUrl}`);
    const receipt = await txResponse.wait();
    if (receipt && receipt.status === 1) {
      return { ...baseResult, status: "success", txHash: txResponse.hash, explorerUrl };
    }
    return {
      ...baseResult,
      status: "failed",
      reason: "Transaction reverted on-chain.",
      txHash: txResponse.hash,
      explorerUrl,
    };
  } catch (err) {
    const e = err as { shortMessage?: string; message?: string };
    return {
      ...baseResult,
      status: "failed",
      reason: e?.shortMessage ?? e?.message ?? String(err),
    };
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((res) => setTimeout(res, ms));
}
