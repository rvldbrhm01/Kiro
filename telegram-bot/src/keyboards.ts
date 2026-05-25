import { Keyboard, InlineKeyboard } from "grammy";

/**
 * Persistent reply keyboard shown under the input field — mirrors the
 * @dnftminttracker_bot main menu layout from the screenshot.
 */
export const mainMenuKeyboard = new Keyboard()
  .text("💼 Wallet").text("🔍 Track NFT").row()
  .text("🔔 Reminders").text("🤖 Auto-Mint").row()
  .text("⛽ Gas").text("🖼️ Portfolio").row()
  .text("📋 Mint History").text("🔥 Trending").row()
  .text("📋 Menu")
  .resized()
  .persistent();

/**
 * Inline keyboard for the welcome message (matches the in-message buttons
 * shown at the top of the screenshot).
 */
export const welcomeInlineKeyboard = new InlineKeyboard()
  .text("💼 My Wallet", "menu:wallet").text("🔍 Track NFT", "menu:track").row()
  .text("🔔 Reminders", "menu:reminders").text("🤖 Auto-Mint", "menu:automint").row()
  .text("⛽ Gas", "menu:gas").text("🖼️ Portfolio", "menu:portfolio").row()
  .text("📋 History", "menu:history").text("🔥 Trending", "menu:trending");

/**
 * Map text-button labels to internal action keys so we can route both
 * reply-keyboard taps and inline-button callbacks through the same handlers.
 */
export const labelToAction: Record<string, string> = {
  "💼 Wallet": "wallet",
  "💼 My Wallet": "wallet",
  "🔍 Track NFT": "track",
  "🔔 Reminders": "reminders",
  "🤖 Auto-Mint": "automint",
  "⛽ Gas": "gas",
  "🖼️ Portfolio": "portfolio",
  "📋 Mint History": "history",
  "📋 History": "history",
  "🔥 Trending": "trending",
  "📋 Menu": "menu",
};
