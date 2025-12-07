import express from "express";
import bodyParser from "body-parser";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(bodyParser.json());

const CLIQ_WEBHOOK_URL = process.env.CLIQ_WEBHOOK_URL;

// Zoho Cliq Webhook Verification Challenge
app.get("/", (req, res) => {
  res.send("Webhook Server Running 🚀");
});

// Receive events from YouTrack
app.post("/youtrack", async (req, res) => {
  try {
    console.log("📩 Incoming Payload:", req.body);

    const issue = req.body.issue;

    const message = {
      text: `Issue ${issue?.idReadable} - ${issue?.summary}
Status: ${issue?.fields?.State || "Unknown"}
Assignee: ${issue?.fields?.Assignee || "Unassigned"}`
    };

    await axios.post(CLIQ_WEBHOOK_URL, message);

    console.log("📤 Notification sent to Zoho Cliq");
    res.status(200).send("OK");
  } catch (error) {
    console.error("❌ Error:", error.message);
    res.status(500).send("Error");
  }
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Server Live on PORT ${PORT}`));
