/**
 * 使用 miniprogram-ci 上传（需私钥）。
 *
 *   WECHAT_UPLOAD_PRIVATE_KEY='-----BEGIN...' WECHAT_APPID=wxc... node scripts/upload.js
 * 或把私钥写到 apps/miniprogram/private.key（勿提交 git）
 */
const fs = require("fs");
const path = require("path");
const ci = require("miniprogram-ci");

const appid = process.env.WECHAT_APPID || "wxc7953007477c1980";
const projectPath = path.resolve(__dirname, "..");
const keyFromEnv = process.env.WECHAT_UPLOAD_PRIVATE_KEY;
const keyPath = path.join(projectPath, "private.key");

if (keyFromEnv) {
  fs.writeFileSync(keyPath, keyFromEnv.replace(/\\n/g, "\n"), { mode: 0o600 });
}

if (!fs.existsSync(keyPath)) {
  console.error("缺少私钥：设置 WECHAT_UPLOAD_PRIVATE_KEY 或写入 private.key");
  process.exit(1);
}

const project = new ci.Project({
  appid,
  type: "miniProgram",
  projectPath,
  privateKeyPath: keyPath,
  ignores: ["node_modules/**/*", "scripts/**/*", "README.md", "SUBMIT.md", "private.key"],
});

(async () => {
  const version = process.env.WECHAT_VERSION || "0.1.0";
  const desc =
    process.env.WECHAT_DESC ||
    "MVP：出题 / 策展进度 / 序章 / 章节阅读 / 演示线";
  const uploadResult = await ci.upload({
    project,
    version,
    desc,
    setting: {
      es6: true,
      minify: true,
      autoPrefixWXSS: true,
    },
    onProgressUpdate: console.log,
  });
  console.log("upload ok", uploadResult);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
