# NFT Mint Tracker Bot

A Telegram bot scaffolded to mirror the menu and feature set of `@dnftminttracker_bot`.
Built with [grammY](https://grammy.dev/) and TypeScript.

## Features (skills)

| Skill         | Command       | Description                                       |
| ------------- | ------------- | ------------------------------------------------- |
| 💼 Wallet      | `/wallet`     | Manage active wallet address                      |
| 🔍 Track NFT   | `/track`      | Subscribe to mint events for an NFT collection    |
| 🔔 Reminders   | `/reminders`  | Set reminders for upcoming mints                  |
| 🤖 Auto-Mint   | `/automint`   | Configure automatic minting on launch             |
| ⛽ Gas         | `/gas`        | Show current gas prices across chains             |
| 🖼️ Portfolio   | `/portfolio`  | View NFTs owned by the active wallet              |
| 📋 Mint History| `/history`    | Show past mints made through the bot              |
| 🔥 Trending    | `/trending`   | List trending mints right now                     |

All blockchain logic is currently stubbed — extend each handler under
`src/handlers/` to integrate the data provider of your choice
(Reservoir, Alchemy, Etherscan, OpenSea, Moralis, etc.).

## Setup

```bash
cp .env.example .env
# Edit .env and paste your BOT_TOKEN from @BotFather

npm install
npm run dev      # development (ts-node)
npm run build    # compile to dist/
npm start        # run compiled bot
```

## Project structure

```
telegram-bot/
├── src/
│   ├── index.ts            # bot entry, registers handlers + menu
│   ├── keyboards.ts        # main menu keyboard layout
│   ├── config.ts           # env loading & validation
│   └── handlers/
│       ├── wallet.ts
│       ├── trackNft.ts
│       ├── reminders.ts
│       ├── autoMint.ts
│       ├── gas.ts
│       ├── portfolio.ts
│       ├── history.ts
│       └── trending.ts
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Notes

- The session/state is in-memory (per process). For production, plug in a
  persistent store (Redis, Postgres) via `grammy`'s session middleware.
- `Auto-Mint` here only stores configuration — actually broadcasting mint
  transactions requires a signing wallet, which is intentionally **not**
  bundled. Use a hot wallet only at your own risk.
