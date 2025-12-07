// Enable CommonJS in ES Module Mode
import express from "express";
import bodyParser from "body-parser";
import fetch from "node-fetch";

const app = express();
const PORT = process.env.PORT || 10000;

app.use(bodyParser.json());

// Your Zoho Cliq Webhook URL
const cliqWebhookUrl =
  "https://cliq.zoho.com/company/906676903/api/v2/channelsbyname/youtracknotificationsw/message?zapikey=1001.48f465d42dd92edf2c111a4c3bfe1e91.a24a042a7cba86673608f042feb2aa18";

// ➜ GET Route - Browser shows service running
app.get("/", (req, res) => {
  res.send(`Webhook Server Running 🚀`);
});

// ➜ POST Route - Receive YouTrack webhooks here
app.post("/webhook", async (req, res) => {
  console.log("📩 Webhook received from YouTrack:", req.body);

  const issue = req.body; // Payload from YouTrack workflow

  const cliqPayload = {
    text: `🆕 Issue Update:\n` +
      `ID: ${issue.id || "N/A"}\n` +
      `Title: ${issue.summary || "N/A"}\n` +
      `Status: ${issue.status || "N/A"}\n` +
      `Priority: ${issue.priority || "N/A"}\n` +
      `Assignee: ${issue.assignee || "N/A"}\n` +
      `Type: ${issue.type || "N/A"}`
  };

  // Send to Zoho Cliq
  try {
    const response = await fetch(cliqWebhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cliqPayload),
    });

    console.log("📤 Sent to Zoho Cliq");
    res.send("Message forwarded to Zoho Cliq!");
  } catch (err) {
    console.error("❌ Error sending to Cliq:", err);
    res.status(500).send("Failed to deliver message to Cliq");
  }
});

// Start Server
app.listen(PORT, () =>
  console.log(`🚀 Server Live on PORT ${PORT}`)
);
