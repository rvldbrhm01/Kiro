# NFT Mint Tracker Bot

A Telegram bot scaffolded to mirror the menu and feature set of
`@dnftminttracker_bot`, with an integrated **SeaDrop FCFS auto-minter** for
Ethereum and Base. Built with [grammY](https://grammy.dev/) and TypeScript.

## Features (skills)

| Skill           | Command       | Description                                       |
| --------------- | ------------- | ------------------------------------------------- |
| 💼 Wallet        | `/wallet`     | Manage active wallet address                      |
| 🔍 Track NFT     | `/track`      | Subscribe to mint events for an NFT collection    |
| 🔔 Reminders     | `/reminders`  | Set reminders for upcoming mints                  |
| 🤖 Auto-Mint     | `/automint`   | Configure watchlist **and run FCFS snipes**       |
| ⛽ Gas           | `/gas`        | Show current gas prices (live)                    |
| 🖼️ Portfolio    | `/portfolio`  | View NFTs owned by the active wallet (stub)       |
| 📋 Mint History  | `/history`    | Past mints made through the bot (stub)            |
| 🔥 Trending      | `/trending`   | Trending mints right now (stub)                   |

Read-only blockchain stubs (`portfolio`, `trending`, `history`) are
placeholders — wire them up to Reservoir / Alchemy / Moralis as you wish.

## Setup

```bash
cp .env.example .env
# Fill in BOT_TOKEN at minimum.
# For the auto-minter, also fill ETH_RPC_URL / BASE_RPC_URL and MINTER_PRIVATE_KEY.

npm install
npm run dev      # development (ts-node)
npm run build    # compile to dist/
npm start        # run compiled bot
```

## OpenSea SeaDrop FCFS auto-minter

Two ways to use it:

### 1. From Telegram

```
/automint snipe <chain> <collection> <qty> [priorityGwei] [maxGwei]
```

Examples:

```
/automint snipe eth  0xCollectionAddress 1
/automint snipe base 0xCollectionAddress 2 5 80
```

The bot reads `getPublicDrop(collection)` from the SeaDrop contract,
waits until `startTime`, then submits an EIP-1559 transaction signed by
`MINTER_PRIVATE_KEY`. Progress logs are sent back as Telegram messages.

### 2. From the CLI

```bash
npm run snipe -- \
  --chain eth \
  --collection 0xCollectionAddress \
  --qty 1 \
  --priority-fee 5 \
  --max-fee 80
```

Add `--dry-run` to read drop config and build the tx without broadcasting.

### How FCFS works here

1. Read `PublicDrop { mintPrice, startTime, endTime, maxPerWallet, feeBps }`
   from `0x00005EA00Ac477B1030CE78506496e8C2dE24bf5` (canonical SeaDrop on
   both Ethereum and Base).
2. Resolve the allowed `feeRecipient` for the collection.
3. Validate window and per-wallet quantity limits.
4. Sleep until `startTime` (minus optional `--preflight` seconds).
5. Submit `mintPublic(nft, feeRecipient, 0x0, qty)` with `value =
   mintPrice * qty` and configurable EIP-1559 fees.

This is **not** a private-mempool / Flashbots bundle — it races the public
mempool. To beat other bots you tune `--priority-fee`. Whoever the validator
includes first wins.

## Security: read this before using the auto-minter

- **Use a dedicated hot wallet.** `MINTER_PRIVATE_KEY` should belong to a
  wallet that holds only what you are willing to spend on mints + gas. Never
  paste the key of your main wallet.
- **Never commit `.env`.** Already in `.gitignore`. Double-check.
- **Verify the collection contract.** Malicious collections can drain
  approvals; this bot only calls `mintPublic` on SeaDrop, but always check.
- **Gas wars are real.** You may pay gas without a successful mint. Set
  `--max-fee` to a value you can afford to lose.
- **The bot does not custody user wallets.** It signs only with the env
  key on the host where the bot runs.

## Project structure

```
telegram-bot/
├── src/
│   ├── index.ts                 # bot entry, registers handlers + menu
│   ├── keyboards.ts             # main menu keyboard layout
│   ├── config.ts                # env loading & validation
│   ├── chains.ts                # ETH / Base chain + SeaDrop config
│   ├── handlers/
│   │   ├── wallet.ts
│   │   ├── trackNft.ts
│   │   ├── reminders.ts
│   │   ├── autoMint.ts          # includes /automint snipe …
│   │   ├── gas.ts
│   │   ├── portfolio.ts
│   │   ├── history.ts
│   │   └── trending.ts
│   ├── snipe/
│   │   ├── seadrop.ts           # SeaDrop ABI + readPublicDrop / pickFeeRecipient
│   │   └── minter.ts            # runFcfsMint — build + sign + broadcast
│   └── cli/
│       └── snipe.ts             # standalone CLI: npm run snipe -- …
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Notes

- Session/state is in-memory per process. Plug in Redis or Postgres via
  grammY's session middleware for production.
- Some collections use SeaDrop 2.0 / `ERC721ShipyardRedeemable` instead of
  SeaDrop 1.0. The current minter targets SeaDrop 1.0 only — extend
  `src/snipe/` if you need other drop standards.
