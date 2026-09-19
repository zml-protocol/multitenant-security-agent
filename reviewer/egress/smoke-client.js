import net from "node:net";
import tls from "node:tls";

const mode = process.argv[2];
const proxyHost = "egress-proxy";
const proxyPort = 3128;
const timeoutMs = 8_000;
const sensitiveSentinel = "SMOKE_SECRET_MUST_NOT_APPEAR";

function finish(result) {
  process.stdout.write(`${JSON.stringify(result)}\n`);
  process.exit(result.passed ? 0 : 1);
}

function connectThroughProxy(target, expectAllowed) {
  const socket = net.createConnection({ host: proxyHost, port: proxyPort });
  socket.setTimeout(timeoutMs);
  let response = Buffer.alloc(0);
  socket.once("connect", () => {
    socket.write(
      `CONNECT ${target} HTTP/1.1\r\nHost: ${target}\r\n` +
      `Proxy-Authorization: Bearer ${sensitiveSentinel}\r\n` +
      `X-Smoke-Sensitive: ${sensitiveSentinel}\r\n\r\n`
    );
  });
  socket.on("data", (chunk) => {
    response = Buffer.concat([response, chunk]);
    const end = response.indexOf("\r\n\r\n");
    if (end === -1) return;
    socket.removeAllListeners("data");
    const statusLine = response.subarray(0, response.indexOf("\r\n")).toString("ascii");
    if (!expectAllowed) {
      socket.destroy();
      finish({ mode, passed: statusLine.includes(" 403 "), status_line: statusLine });
      return;
    }
    if (!statusLine.includes(" 200 ")) {
      socket.destroy();
      finish({ mode, passed: false, status_line: statusLine });
      return;
    }
    const secure = tls.connect({ socket, servername: "api.anthropic.com", rejectUnauthorized: true });
    secure.setTimeout(timeoutMs);
    secure.once("secureConnect", () => {
      const authorized = secure.authorized;
      secure.end();
      finish({ mode, passed: authorized, status_line: statusLine, tls_authorized: authorized });
    });
    secure.once("timeout", () => finish({ mode, passed: false, reason: "tls_timeout" }));
    secure.once("error", () => finish({ mode, passed: false, reason: "tls_error" }));
  });
  socket.once("timeout", () => finish({ mode, passed: false, reason: "proxy_timeout" }));
  socket.once("error", () => finish({ mode, passed: false, reason: "proxy_error" }));
}

function testDirectConnection() {
  const socket = net.createConnection({ host: "api.anthropic.com", port: 443 });
  socket.setTimeout(4_000);
  socket.once("connect", () => {
    socket.destroy();
    finish({ mode, passed: false, direct_connection: "unexpectedly_connected" });
  });
  socket.once("timeout", () => {
    socket.destroy();
    finish({ mode, passed: true, direct_connection: "blocked" });
  });
  socket.once("error", () => finish({ mode, passed: true, direct_connection: "blocked" }));
}

if (mode === "allowed") connectThroughProxy("api.anthropic.com:443", true);
else if (mode === "blocked") connectThroughProxy("example.com:443", false);
else if (mode === "direct") testDirectConnection();
else finish({ mode, passed: false, reason: "unknown_mode" });
