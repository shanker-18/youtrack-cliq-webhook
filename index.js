const express = require("express");
const app = express();
const PORT = process.env.PORT || 10000;

app.use(express.json());

// 👇 This is required endpoint YouTrack is calling
app.post("/webhook", (req, res) => {
  console.log("📩 Webhook received from YouTrack:", req.body);

  res.status(200).send("Webhook received successfully!");
});

// Basic home route
app.get("/", (req, res) => {
  res.send("Webhook Server Running 🚀");
});

// Start Server
app.listen(PORT, () => {
  console.log(`🚀 Server Live on PORT ${PORT}`);
});
