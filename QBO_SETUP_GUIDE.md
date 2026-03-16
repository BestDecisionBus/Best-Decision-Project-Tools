# QuickBooks Online Integration — Setup Guide

This guide walks you through the external steps needed to connect BDB Project Tools to QuickBooks Online so you can push estimates and invoices directly from the app.

---

## 1. Create an Intuit Developer Account

1. Go to **https://developer.intuit.com** and sign in (or create a free account).
2. If prompted, agree to the Intuit Developer terms of service.

## 2. Create an App in the Intuit Developer Portal

1. From the developer dashboard, click **Create an app**.
2. Choose **QuickBooks Online and Payments** as the platform.
3. Give your app a name (e.g. "BDB Project Tools").
4. Once created, you'll land on the app's **Dashboard** page.

## 3. Get Your Client ID and Client Secret

1. In your app dashboard, go to the **Keys & credentials** section.
2. You'll see two environments: **Sandbox** and **Production**.
   - Start with **Sandbox** for testing — it comes with a free test company.
   - Switch to **Production** when you're ready for real data.
3. Copy the **Client ID** and **Client Secret** for the environment you're using.

## 4. Configure the Redirect URI

1. Still in **Keys & credentials**, scroll to **Redirect URIs**.
2. Add your app's OAuth callback URL:
   - **Sandbox/dev:** `https://yourdomain.com/admin/qbo/callback`
   - **Production:** same pattern — must match exactly what you set in `.env`
3. The redirect URI must use **HTTPS** (Intuit requires it). If you're testing locally, use a tool like ngrok to get an HTTPS tunnel.

## 5. Generate an Encryption Key

The app encrypts QBO OAuth tokens at rest using Fernet symmetric encryption. Generate a key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save this key — you'll need it for the `.env` file. **Do not lose it.** If you change it, all stored QBO tokens become unreadable and every company will need to reconnect.

## 6. Set Environment Variables

Add these to your `.env` file:

```env
# QuickBooks Online (OAuth2)
QBO_CLIENT_ID=your-client-id-from-intuit
QBO_CLIENT_SECRET=your-client-secret-from-intuit
QBO_REDIRECT_URI=https://yourdomain.com/admin/qbo/callback
QBO_ENVIRONMENT=sandbox
QBO_ENCRYPTION_KEY=your-fernet-key-from-step-5
```

- Set `QBO_ENVIRONMENT` to `sandbox` for testing or `production` for real QuickBooks data.
- `QBO_REDIRECT_URI` must **exactly match** what you entered in the Intuit developer portal (Step 4).

## 7. Restart the Service

After updating `.env`, restart the app so the new config is loaded:

```bash
sudo systemctl restart bdpt
```

## 8. Connect a Company in the App

1. Log in as an admin.
2. Select the company (token) you want to connect.
3. Go to **Admin tab > Settings**.
4. Scroll to the **QuickBooks Online** section.
5. Click **Connect to QuickBooks** — you'll be redirected to Intuit to authorize.
6. Sign in to your QuickBooks account and grant access.
7. You'll be redirected back to Settings with a "Connected" confirmation.

## 9. Start Pushing Data

Once connected, you'll see **Send to QuickBooks** buttons on:

- **Estimate detail pages** — pushes the estimate and its line items
- **Invoice detail pages** — pushes the invoice and its line items

The app automatically creates customers in QuickBooks if they don't already exist.

---

## Going to Production

When you're ready to use real QuickBooks data:

1. In the Intuit developer portal, go to your app and complete the **Production** requirements (Intuit may require a brief review).
2. Copy the **Production** Client ID and Client Secret.
3. Update your `.env`:
   - Replace `QBO_CLIENT_ID` and `QBO_CLIENT_SECRET` with the production values.
   - Change `QBO_ENVIRONMENT=production`.
   - Update `QBO_REDIRECT_URI` if your production domain is different.
4. Restart the service (`sudo systemctl restart bdpt`).
5. Each company will need to reconnect via Admin > Settings > Connect to QuickBooks.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "QuickBooks integration is not configured" | `QBO_CLIENT_ID` or `QBO_REDIRECT_URI` is empty in `.env`. |
| OAuth redirect fails / 400 error | `QBO_REDIRECT_URI` in `.env` doesn't exactly match the one in the Intuit portal. |
| "OAuth state mismatch" | Session expired — try connecting again. |
| Token refresh errors | The refresh token may have expired (100 days if unused). Disconnect and reconnect. |
| "Failed to decrypt QBO token" | `QBO_ENCRYPTION_KEY` was changed. Companies must reconnect. |
| Duplicate customer errors | The app handles this automatically by looking up the existing QBO customer. |

## Sandbox Testing

Intuit provides a free sandbox company when you create a developer account. Use it to test the full flow without touching real books. The sandbox company comes pre-loaded with sample customers, items, and transactions. Access it at **https://app.sandbox.qbo.intuit.com**.
