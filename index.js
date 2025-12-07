import express from "express";
import axios from "axios";

const app = express();
app.use(express.json());

app.get("/", (req, res) => {
  res.send("Webhook Server Running 🚀");
});

// Zoho Cliq Webhook URL
const CLIQ_WEBHOOK_URL =
  "https://cliq.zoho.com/company/906676903/api/v2/channelsbyname/youtracknotificationsw/message?zapikey=1001.48f465d42dd92edf2c111a4c3bfe1e91.a24a042a7cba86673608f042feb2aa18";

app.post("/webhook", async (req, res) => {
  console.log("📩 Webhook received from YouTrack:", req.body);

  try {
    const issue = req.body;

    const message = {
      text: `🆕 Issue Update:
ID: ${issue.id}
Title: ${issue.summary}
Status: ${issue.status}
Priority: ${issue.priority}
Assignee: ${issue.assignee}
Type: ${issue.type}`
    };

    const response = await axios.post(CLIQ_WEBHOOK_URL, message);

    console.log("📤 Sent to Zoho Cliq:", response.data);

    res.status(200).send("Message forwarded to Zoho Cliq!");
  } catch (err) {
    console.error("❌ Error sending to Cliq:", err.message);
    res.status(500).send("Failed to forward to Zoho Cliq");
  }
});

// Render assigned PORT
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`🚀 Server Live on PORT ${PORT}`));
