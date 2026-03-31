/**
 * Trigger Apify webhook from Google Sheets
 *
 * Setup:
 * 1. Open your Google Sheet
 * 2. Extensions > Apps Script
 * 3. Paste this code
 * 4. Save and run scrapeLeads()
 */

function scrapeLeads() {
  // Your webhook URL
  var webhookUrl = "https://giabaongb0305--anti-gravity-webhook-scrape-webhook.modal.run";

  // Get values from sheet (optional)
  var sheet = SpreadsheetApp.getActiveSheet();
  // Example: Read industry from cell A2
  // var industry = sheet.getRange("A2").getValue();

  // Or hardcode values
  var industry = "Marketing Agency";
  var fetchCount = 30;

  var payload = {
    "industry": industry,
    "fetch_count": fetchCount,
    "location": "united states",
    "company_keywords": ["digital marketing", "PPC"]
  };

  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload)
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());

    Logger.log("✅ Success!");
    Logger.log("Job ID: " + result.job_id);
    Logger.log("Industry: " + result.industry);

    // Show success message in sheet
    Browser.msgBox("Lead scraping started! Job ID: " + result.job_id);

  } catch (error) {
    Logger.log("❌ Error: " + error);
    Browser.msgBox("Error: " + error);
  }
}

/**
 * Add custom menu to Google Sheets
 */
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('🚀 Lead Scraper')
      .addItem('Scrape Leads', 'scrapeLeads')
      .addToUi();
}
