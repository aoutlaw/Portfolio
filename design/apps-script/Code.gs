/**
 * designoutlaw.com — contact form endpoint.
 *
 * Receives a POST from the site's contact form, appends a row to this
 * spreadsheet, and emails the message on. Deployed as a web app.
 *
 * Setup steps are in README.md next to this file.
 */

// Where notifications go. Change this and re-deploy if the address changes.
var NOTIFY = 'angelo.outlaw@gmail.com';
var SHEET_NAME = 'Messages';

function doPost(e) {
  try {
    var p = (e && e.parameter) || {};

    // Honeypot. Bots fill hidden fields; people never see this one. Answer
    // with a success so the bot has nothing to learn from the response.
    if (p.company) {
      return json({ ok: true });
    }

    var name = String(p.name || '').trim();
    var email = String(p.email || '').trim();
    var message = String(p.message || '').trim();

    if (!name || !email || !message) {
      return json({ ok: false, error: 'Please fill in every field.' });
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return json({ ok: false, error: 'That email address is not valid.' });
    }
    // Cheap guard against someone pasting a novel into the box.
    if (message.length > 5000) {
      message = message.slice(0, 5000) + '\n\n[truncated]';
    }

    appendRow(name, email, message);
    notify(name, email, message);

    return json({ ok: true });
  } catch (err) {
    // Logged to the Apps Script execution log, not shown to the visitor.
    console.error(err);
    return json({ ok: false, error: 'Something went wrong on our end.' });
  }
}

/** A GET is someone opening the URL in a browser; make that harmless. */
function doGet() {
  return json({ ok: true, note: 'Contact endpoint. POST only.' });
}

function appendRow(name, email, message) {
  var book = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = book.getSheetByName(SHEET_NAME) || book.insertSheet(SHEET_NAME);

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Received', 'Name', 'Email', 'Message']);
    sheet.getRange('A1:D1').setFontWeight('bold');
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 160);
    sheet.setColumnWidth(2, 180);
    sheet.setColumnWidth(3, 240);
    sheet.setColumnWidth(4, 560);
  }

  sheet.appendRow([new Date(), name, email, message]);
}

function notify(name, email, message) {
  MailApp.sendEmail({
    to: NOTIFY,
    subject: 'designoutlaw.com — message from ' + name,
    // Replying in your mail client goes straight back to the sender.
    replyTo: email,
    body:
      name + ' <' + email + '>\n\n' +
      message + '\n\n' +
      '—\nSent from the contact form at designoutlaw.com',
  });
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Run this once from the editor to check the Sheet and email both work,
 * without going near the website. It sends you one test message.
 */
function selfTest() {
  appendRow('Test Person', 'test@example.com', 'This is a test message.');
  notify('Test Person', 'test@example.com', 'This is a test message.');
}
