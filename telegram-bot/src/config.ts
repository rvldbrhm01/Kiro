import * as dotenv from "dotenv";

dotenv.config();

function required(name: string): string {
  const value = process.env[name];
  if (!value || value.trim() === "") {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value;
}

function optional(name: string, fallback = ""): string {
  return process.env[name]?.trim() || fallback;
}

export const config = {
  botToken: required("BOT_TOKEN"),
  etherscanKey: optional("ETHERSCAN_API_KEY"),
  alchemyKey: optional("ALCHEMY_API_KEY"),
  reservoirKey: optional("RESERVOIR_API_KEY"),
  defaultChain: optional("DEFAULT_CHAIN", "ethereum"),
};
