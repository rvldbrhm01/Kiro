import { ethers } from "ethers";

/**
 * Minimal SeaDrop 1.0 interface — only the calls the FCFS minter needs.
 * Full source: https://github.com/ProjectOpenSea/seadrop
 */
export const SEADROP_ABI = [
  "function mintPublic(address nftContract, address feeRecipient, address minterIfNotPayer, uint256 quantity) external payable",
  "function getPublicDrop(address nftContract) external view returns (tuple(uint80 mintPrice, uint48 startTime, uint48 endTime, uint16 maxTotalMintableByWallet, uint16 feeBps, bool restrictFeeRecipients))",
  "function getAllowedFeeRecipients(address nftContract) external view returns (address[])",
] as const;

export interface PublicDrop {
  mintPrice: bigint;
  startTime: number; // unix seconds
  endTime: number; // unix seconds
  maxTotalMintableByWallet: number;
  feeBps: number;
  restrictFeeRecipients: boolean;
}

export async function readPublicDrop(
  seaDrop: ethers.Contract,
  nftContract: string,
): Promise<PublicDrop> {
  const r = await seaDrop.getPublicDrop(nftContract);
  return {
    mintPrice: BigInt(r[0]),
    startTime: Number(r[1]),
    endTime: Number(r[2]),
    maxTotalMintableByWallet: Number(r[3]),
    feeBps: Number(r[4]),
    restrictFeeRecipients: Boolean(r[5]),
  };
}

export async function pickFeeRecipient(
  seaDrop: ethers.Contract,
  nftContract: string,
): Promise<string> {
  const recips: string[] = await seaDrop.getAllowedFeeRecipients(nftContract);
  if (!recips || recips.length === 0) {
    throw new Error(
      "No allowed fee recipients configured for this collection. " +
        "It may not use the standard SeaDrop drop, or the drop is not finalized yet.",
    );
  }
  return recips[0];
}
