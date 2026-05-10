import http from "node:http";

const url = "http://127.0.0.1:8787/api/health/deep";

http
  .get(url, (res) => {
    let body = "";
    res.on("data", (chunk) => (body += chunk));
    res.on("end", () => {
      console.log(body);
      process.exit(res.statusCode === 200 ? 0 : 1);
    });
  })
  .on("error", (error) => {
    console.error(`Backend check failed: ${error.message}`);
    process.exit(1);
  });
