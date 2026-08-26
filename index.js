const express = require("express");
const bodyParser = require("body-parser");
const axios = require("axios");

const app = express();
const PORT = process.env.PORT || 10000;


app.use(bodyParser.json());

// ✅ Your Zoho Cliq webhook URL
const CLIQ_WEBHOOK_URL =
  "https://cliq.zoho.com/company/906676903/api/v2/channelsbyname/youtracknotificationsw/message?zapikey=1001.48f465d42dd92edf2c111a4c3bfe1e91.a24a042a7cba86673608f042feb2aa18";

// just to test in browser
app.get("/", (req, res) => {
  res.send("Webhook Server Running 🚀");
});

// YouTrack → here
app.post("/webhook", async (req, res) => {
  console.log("📩 Webhook received from YouTrack:", req.body);
  const issue = req.body || {};

  const cliqMessage = {
    text:
      `🆕 Issue Update:\n` +
      `ID: ${issue.id || "N/A"}\n` +
      `Title: ${issue.summary || "N/A"}\n` +
      `Status: ${issue.status || "N/A"}\n` +
      `Priority: ${issue.priority || "N/A"}\n` +
      `Assignee: ${issue.assignee || "N/A"}\n` +
      `Type: ${issue.type || "N/A"}`
  };

  try {
    const resp = await axios.post(CLIQ_WEBHOOK_URL, cliqMessage, {
      headers: { "Content-Type": "application/json" }
    });

    console.log("📤 Sent to Zoho Cliq:", resp.status);
    res.send("Message forwarded to Zoho Cliq!");
  } catch (err) {
    console.error("❌ Error sending to Zoho Cliq:", err.message);
    res.status(500).send("Failed to send to Zoho Cliq");
  }
});

app.listen(PORT, () => {
  console.log(`🚀 Server Live on PORT ${PORT}`);
});
