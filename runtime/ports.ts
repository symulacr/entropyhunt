import * as net from "node:net";

async function canBind(host: string, port: number): Promise<boolean> {
  return await new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.listen({ host, port, exclusive: true }, () => {
      server.close(() => resolve(true));
    });
  });
}

export async function findFreePort(host: string): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once("error", reject);
    server.listen({ host, port: 0, exclusive: true }, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Unable to determine ephemeral port"));
        return;
      }
      const { port } = address;
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(port);
      });
    });
  });
}

export async function findContiguousPortRange(host: string, count: number, start = 20000, end = 60000): Promise<number> {
  if (count <= 0) {
    throw new Error(`count must be positive; received ${count}`);
  }

  for (let base = start; base <= end - count; base += 1) {
    let available = true;
    for (let offset = 0; offset < count; offset += 1) {
      const open = await canBind(host, base + offset);
      if (!open) {
        available = false;
        break;
      }
    }
    if (available) {
      return base;
    }
  }

  throw new Error(`Unable to find contiguous free port range of size ${count} on ${host}`);
}
