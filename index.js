import express from "express";

const app = express();
const PORT = process.env.PORT || 10000;

app.use(express.json());

app.post("/webhook", (req, res) => {
  console.log("📩 Webhook received from YouTrack:", req.body);
  res.status(200).send("Webhook received successfully!");
});

app.get("/", (req, res) => {
  res.send("Webhook Server Running 🚀");
});

app.listen(PORT, () => {
  console.log(`🚀 Server Live on PORT ${PORT}`);
});
