# Contact form endpoint — setup

The contact form posts to a Google Apps Script web app, which appends a row to a
spreadsheet in your Drive and emails the message to `angelo.outlaw@gmail.com`. Five
minutes, once. (Same pattern as firefighterpfister's contact form — see that repo's
`design/apps-script/` if you want to compare.)

## 1. Make the spreadsheet

1. Go to [sheets.new](https://sheets.new)
2. Name it something like **designoutlaw.com — Messages**

The script creates its own `Messages` tab with headers on the first submission, so
there is nothing to set up inside the sheet.

## 2. Add the script

1. In that spreadsheet: **Extensions → Apps Script**
2. Delete the `function myFunction() {}` stub that's there
3. Paste the entire contents of `Code.gs` from this folder
4. **Save** (the disk icon)

## 3. Check it works before wiring up the site

1. In the editor's function dropdown, choose **selfTest**, then **Run**
2. Google will ask for authorization the first time — approve it. It will warn that
   the app isn't verified; that's expected for your own script. Choose
   **Advanced → Go to (project name)**.
3. Confirm a row appeared in the sheet and a test email reached
   `angelo.outlaw@gmail.com`

If both happened, the hard part is done.

## 4. Deploy it

1. **Deploy → New deployment**
2. Click the gear next to "Select type" and choose **Web app**
3. Set:
   - **Execute as:** Me
   - **Who has access:** **Anyone**
4. **Deploy**, approve access again if asked
5. Copy the **Web app URL** — it ends in `/exec`

> "Anyone" sounds alarming but is required: visitors aren't signed into Google. It
> only lets people POST a message; the script never exposes the sheet.

## 5. Wire it into the site

Open `build.py` and replace the placeholder in `CONTACT_FORM_ENDPOINT` with the URL
from step 4, then rebuild (`python3 build.py`) and redeploy. Until that's done, the
form on the built site shows a "not connected yet" message instead of silently
swallowing submissions.

## Changing things later

- **Different notification address:** edit `NOTIFY` at the top of `Code.gs`
- **After any edit:** **Deploy → Manage deployments → edit (pencil) → Version: New
  version → Deploy.** The URL stays the same. Editing without re-deploying changes
  nothing on the live site — this is the step people miss.
