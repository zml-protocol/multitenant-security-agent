import dns from "node:dns";
import net from "node:net";

const allowedHost = "api.anthropic.com";
const allowedPort = 443;
const listenPort = 3128;
const maximumHeaderBytes = 16 * 1024;
const socketTimeoutMs = 120_000;

function log(decision, target, reason) {
  process.stdout.write(`${JSON.stringify({
    timestamp: new Date().toISOString(),
    event: "connect_decision",
    decision,
    target,
    reason,
  })}\n`);
}

function isPublicIpv4(address) {
  const octets = address.split(".").map(Number);
  if (octets.length !== 4 || octets.some((value) => !Number.isInteger(value) || value < 0 || value > 255)) {
    return false;
  }
  const [a, b, c] = octets;
  if (a === 0 || a === 10 || a === 127 || a >= 224) return false;
  if (a === 100 && b >= 64 && b <= 127) return false;
  if (a === 169 && b === 254) return false;
  if (a === 172 && b >= 16 && b <= 31) return false;
  if (a === 192 && b === 168) return false;
  if (a === 192 && b === 0 && (c === 0 || c === 2)) return false;
  if (a === 198 && (b === 18 || b === 19 || b === 51)) return false;
  if (a === 203 && b === 0 && c === 113) return false;
  return true;
}

function deny(client, status, target, reason) {
  log("deny", target, reason);
  client.end(`HTTP/1.1 ${status}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
}

function connectAllowedTarget(client, target, bufferedAfterHeaders) {
  dns.lookup(allowedHost, { all: true, family: 4 }, (lookupError, addresses) => {
    if (lookupError) {
      deny(client, "502 Bad Gateway", target, "dns_failure");
      return;
    }
    const resolved = addresses.find((candidate) => isPublicIpv4(candidate.address));
    if (!resolved) {
      deny(client, "502 Bad Gateway", target, "no_public_ipv4");
      return;
    }

    let established = false;
    const upstream = net.createConnection({ host: resolved.address, port: allowedPort, family: 4 });
    upstream.setTimeout(socketTimeoutMs);
    upstream.once("connect", () => {
      established = true;
      log("allow", target, "allowlist_match");
      client.write("HTTP/1.1 200 Connection Established\r\n\r\n");
      if (bufferedAfterHeaders.length) upstream.write(bufferedAfterHeaders);
      client.pipe(upstream);
      upstream.pipe(client);
    });
    upstream.once("timeout", () => upstream.destroy(new Error("upstream_timeout")));
    upstream.once("error", () => {
      if (client.destroyed) return;
      if (established) client.destroy();
      else deny(client, "502 Bad Gateway", target, "upstream_failure");
    });
  });
}

const server = net.createServer((client) => {
  client.setTimeout(socketTimeoutMs);
  let buffered = Buffer.alloc(0);

  const receiveHeaders = (chunk) => {
    buffered = Buffer.concat([buffered, chunk]);
    if (buffered.length > maximumHeaderBytes) {
      client.removeListener("data", receiveHeaders);
      deny(client, "431 Request Header Fields Too Large", "invalid", "header_limit");
      return;
    }
    const headerEnd = buffered.indexOf("\r\n\r\n");
    if (headerEnd === -1) return;

    client.removeListener("data", receiveHeaders);
    const firstLineEnd = buffered.indexOf("\r\n");
    const firstLine = buffered.subarray(0, firstLineEnd).toString("ascii");
    const match = /^CONNECT ([A-Za-z0-9.-]+):(\d+) HTTP\/1\.[01]$/.exec(firstLine);
    if (!match) {
      deny(client, "405 Method Not Allowed", "invalid", "connect_required");
      return;
    }

    const host = match[1].toLowerCase();
    const port = Number(match[2]);
    const target = `${host}:${port}`;
    if (host !== allowedHost || port !== allowedPort) {
      deny(client, "403 Forbidden", target, "not_allowlisted");
      return;
    }
    connectAllowedTarget(client, target, buffered.subarray(headerEnd + 4));
  };

  client.on("data", receiveHeaders);
  client.once("timeout", () => deny(client, "408 Request Timeout", "invalid", "client_timeout"));
  client.once("error", () => {});
});

server.maxConnections = 32;
server.listen(listenPort, "0.0.0.0", () => {
  process.stdout.write(`${JSON.stringify({
    timestamp: new Date().toISOString(),
    event: "proxy_ready",
    listen_port: listenPort,
    allowed_target: `${allowedHost}:${allowedPort}`,
  })}\n`);
});
