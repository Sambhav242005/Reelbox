# Reelbox Chromium extension

Works with normal profiles in Microsoft Edge, Google Chrome and Brave. It reuses the Instagram login in the profile where you install it.

## Install locally

1. Start the Reelbox app with `Start Reelbox.cmd` in the repository root.
2. Open `edge://extensions`, `chrome://extensions` or `brave://extensions` in your usual browser.
3. Enable **Developer mode**, choose **Load unpacked**, and select this `extension` folder.
4. Open Instagram â†’ your profile â†’ **Saved** in that browser.
5. Click the Reelbox extension icon and **Connect this Saved page**.

The extension pairs with the local dashboard, copies the current Instagram session to the local downloader, and starts a scan in an inactive tab. That tab closes after scanning. No separate browser profile or second login is needed.

The extension checks once per minute for local sync requests and whether today's scan has completed. It syncs once per day when the browser and local app are both running. **Sync now** forces a scan. It cannot run with the browser closed.

Each Saved page starts from the top and scrolls downward in viewport steps. Links are submitted in visual row order with a shared scan timestamp and ascending positions; those positions drive the backend queue and default reel list. Available image URLs are submitted for thumbnail caching. The backend retries missing metadata/images up to ten times, then notifies you in Reelbox.

Install in the profile containing the Instagram account you want. Pairing more than one account/browser to the same library is not an account-isolated workflow; use one primary profile for scheduled sync.

## Permissions

- **Instagram host access**: read links from your Saved page and access Instagram cookies.
- **Localhost host access**: connect only to your local Reelbox service at `127.0.0.1:8765`.
- **Cookies**: pass only Instagram cookies to that local service so Instaloader can retrieve accessible post metadata and resolve videos when needed. No cookies are sent to models or stored in extension storage.
- **Tabs**: open the local pairing tab and an inactive Saved scan tab, then close tabs created by the extension.
- **Scripting**: read the local API token from the dashboard during your explicit Connect action.
- **Storage**: remember the Saved URL, local pairing token, daily completion and scan progress.
- **Alarms**: schedule daily checks and reconnect when the local app starts.

The Instagram cookie file under Reelbox's `data` folder contains login credentials. Keep it private. The collector also submits available cover URLs and image alt text to the local backend. The backend sends captions, covers, sampled frames, transcripts and category evidence to local MiniCPM inference (or the explicitly configured decision model) with the default configuration. It never includes Instagram cookies or the pairing token in model requests. Explicitly configured remote endpoints can change where inference occurs.

This extension does not modify saves or post content, solve challenges or bypass Instagram access controls. Page-layout changes, challenges, session expiry and throttling may interrupt scans. A capped scan is reported as partial. After updating the extension files, use Reload in your browser's extensions page.

This is an unpacked local extension, not a published or store-reviewed release. Automated checks cover code and local message handling; actual Instagram collection requires installation and an account test.
