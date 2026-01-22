import { describe, it, expect, beforeEach, mock, spyOn } from 'bun:test';
import { Transport, RemoteEnvelope } from '../../src/remote/transport';
import type { Serializer } from '../../src/remote/serialization';
import type { ActorSystem } from '../../src/core/actor-system';
import type { ActorAddress } from '../../src/types/actor.types';
import type { AnyMessage } from '../../src/types/message.types';
import type { TCPSocket, TCPServer } from 'bun';

const mockBun = {
  listen: mock((options: any): TCPServer => {
    return {
      stop: mock(() => {}),
      ref: mock(() => {}),
      unref: mock(() => {}),
      port: options.port,
      hostname: options.hostname,
    } as unknown as TCPServer;
  }),
  connect: mock((options: any): Promise<TCPSocket> => {
    const socket = {
      write: mock((data: Buffer) => data.length),
      end: mock(() => {}),
      ref: mock(() => {}),
      unref: mock(() => {}),
      data: options.socket,
    } as unknown as TCPSocket;
    return Promise.resolve(socket);
  }),
};

mock.module('bun', () => mockBun);

describe('Transport', () => {
  let mockActorSystem: ActorSystem;
  let mockSerializer: Serializer;
  let transport: Transport;
  const host = '127.0.0.1';
  const port = 8080;

  beforeEach(() => {
    mockBun.listen.mockClear();
    mockBun.connect.mockClear();

    mockActorSystem = {
      deliverRemote: mock(() => {}),
    } as unknown as ActorSystem;

    mockSerializer = {
      serialize: mock((msg: AnyMessage) => Buffer.from(JSON.stringify(msg))),
      deserialize: mock((buf: Buffer) => JSON.parse(buf.toString())),
    };

    transport = new Transport(mockActorSystem, mockSerializer, host, port);
  });

  describe('Server Lifecycle', () => {
    it('should not have a server instance before start is called', () => {
      expect((transport as any).server).toBeNull();
    });

    it('should start a TCP server on the specified host and port', async () => {
      await transport.start();
      expect(mockBun.listen).toHaveBeenCalledWith({
        hostname: host,
        port: port,
        socket: {
          open: expect.any(Function),
          data: expect.any(Function),
          close: expect.any(Function),
          error: expect.any(Function),
        },
      });
      expect((transport as any).server).not.toBeNull();
    });

    it('should throw an error if start is called when server is already running', async () => {
      await transport.start();
      await expect(transport.start()).rejects.toThrow('Server is already running');
    });

    it('should stop the running server', async () => {
      await transport.start();
      const server = (transport as any).server;
      const stopSpy = spyOn(server, 'stop');
      await transport.stop();
      expect(stopSpy).toHaveBeenCalled();
      expect((transport as any).server).toBeNull();
    });

    it('should do nothing if stop is called when no server is running', async () => {
      await expect(transport.stop()).toResolve();
      expect((transport as any).server).toBeNull();
    });
  });

  describe('Sending Messages', () => {
    const targetAddress: ActorAddress = { host: 'remotehost', port: 9090, path: '/user/receiver' };
    const senderAddress: ActorAddress = { host: 'localhost', port: 8080, path: '/user/sender' };
    const message: RemoteEnvelope = {
      target: targetAddress,
      sender: senderAddress,
      message: { type: 'test', payload: 'hello' },
    };
    const serializedMessage = Buffer.from(JSON.stringify(message));
    const messageLength = Buffer.alloc(4);
    messageLength.writeUInt32BE(serializedMessage.length, 0);
    const framedMessage = Buffer.concat([messageLength, serializedMessage]);

    it('should connect, serialize, frame, and send a message to a new remote', async () => {
      const socket = await mockBun.connect.mock.results[0].value;
      await transport.send(message);

      expect(mockBun.connect).toHaveBeenCalledWith({
        hostname: targetAddress.host,
        port: targetAddress.port,
        socket: expect.any(Object),
      });

      const connectedSocket = (transport as any).clients.get(`${targetAddress.host}:${targetAddress.port}`);
      expect(connectedSocket).toBeDefined();

      expect(mockSerializer.serialize).toHaveBeenCalledWith(message);
      expect(connectedSocket.write).toHaveBeenCalledWith(framedMessage);
    });

    it('should use an existing connection to send a subsequent message', async () => {
      await transport.send(message);
      const connectedSocket = (transport as any).clients.get(`${targetAddress.host}:${targetAddress.port}`);

      mockBun.connect.mockClear();
      (connectedSocket.write as jest.Mock).mockClear();

      const anotherMessage = { ...message, message: { type: 'test2', payload: 'world' } };
      await transport.send(anotherMessage);

      expect(mockBun.connect).not.toHaveBeenCalled();

      const serializedAnotherMessage = Buffer.from(JSON.stringify(anotherMessage));
      const anotherLength = Buffer.alloc(4);
      anotherLength.writeUInt32BE(serializedAnotherMessage.length, 0);
      const framedAnotherMessage = Buffer.concat([anotherLength, serializedAnotherMessage]);
      expect(connectedSocket.write).toHaveBeenCalledWith(framedAnotherMessage);
    });

    it('should log an error if connection fails', async () => {
      const consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
      mockBun.connect.mockImplementationOnce(async () => {
        throw new Error('Connection refused');
      });

      await transport.send(message);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        `[Transport] Failed to connect to ${targetAddress.host}:${targetAddress.port}:`,
        expect.any(Error)
      );
      consoleErrorSpy.mockRestore();
    });

    it('should remove a client from the cache when its connection is closed', async () => {
      await transport.send(message);
      const remoteKey = `${targetAddress.host}:${targetAddress.port}`;
      expect((transport as any).clients.has(remoteKey)).toBe(true);
      const socket = (transport as any).clients.get(remoteKey);

      const connectOptions = mockBun.connect.mock.calls[0][0];
      connectOptions.socket.close(socket);

      expect((transport as any).clients.has(remoteKey)).toBe(false);
    });
  });

  describe('Receiving Messages', () => {
    let socketHandlers: any;
    let mockServerSocket: TCPSocket;

    beforeEach(async () => {
      const server = mockBun.listen.mock.results[0].value;
      (mockBun.listen as jest.Mock).mockImplementation((options: any) => {
        socketHandlers = options.socket;
        return server;
      });
      await transport.start();
      mockServerSocket = { id: 'mock-socket-1' } as unknown as TCPSocket;
      socketHandlers.open(mockServerSocket);
    });

    const targetAddress: ActorAddress = { host, port, path: '/user/receiver' };
    const senderAddress: ActorAddress = { host: 'remotehost', port: 9090, path: '/user/sender' };
    const envelope: RemoteEnvelope = {
      target: targetAddress,
      sender: senderAddress,
      message: { type: 'test', payload: 'data' },
    };

    it('should process a single complete message', () => {
      const serialized = (mockSerializer.serialize as jest.Mock)(envelope);
      const length = Buffer.alloc(4);
      length.writeUInt32BE(serialized.length, 0);
      const framed = Buffer.concat([length, serialized]);

      socketHandlers.data(mockServerSocket, framed);

      expect(mockSerializer.deserialize).toHaveBeenCalledWith(serialized);
      expect(mockActorSystem.deliverRemote).toHaveBeenCalledWith(envelope);
    });

    it('should process multiple complete messages in a single data chunk', () => {
      const envelope2: RemoteEnvelope = { ...envelope, message: { type: 'test2' } };
      const serialized1 = (mockSerializer.serialize as jest.Mock)(envelope);
      const length1 = Buffer.alloc(4);
      length1.writeUInt32BE(serialized1.length, 0);
      const framed1 = Buffer.concat([length1, serialized1]);

      const serialized2 = (mockSerializer.serialize as jest.Mock)(envelope2);
      const length2 = Buffer.alloc(4);
      length2.writeUInt32BE(serialized2.length, 0);
      const framed2 = Buffer.concat([length2, serialized2]);

      const combinedChunk = Buffer.concat([framed1, framed2]);

      socketHandlers.data(mockServerSocket, combinedChunk);

      expect(mockSerializer.deserialize).toHaveBeenCalledTimes(2);
      expect(mockSerializer.deserialize).toHaveBeenCalledWith(serialized1);
      expect(mockSerializer.deserialize).toHaveBeenCalledWith(serialized2);
      expect(mockActorSystem.deliverRemote).toHaveBeenCalledTimes(2);
      expect(mockActorSystem.deliverRemote).toHaveBeenCalledWith(envelope);
      expect(mockActorSystem.deliverRemote).toHaveBeenCalledWith(envelope2);
    });

    it('should buffer and process a message split across multiple data chunks', () => {
      const serialized = (mockSerializer.serialize as jest.Mock)(envelope);
      const length = Buffer.alloc(4);
      length.writeUInt32BE(serialized.length, 0);
      const framed = Buffer.concat([length, serialized]);
      const chunk1 = framed.subarray(0, 10);
      const chunk2 = framed.subarray(10);

      socketHandlers.data(mockServerSocket, chunk1);
      expect(mockSerializer.deserialize).not.toHaveBeenCalled();
      expect(mockActorSystem.deliverRemote).not.toHaveBeenCalled();

      socketHandlers.data(mockServerSocket, chunk2);
      expect(mockSerializer.deserialize).toHaveBeenCalledWith(serialized);
      expect(mockActorSystem.deliverRemote).toHaveBeenCalledWith(envelope);
    });

    it('should log an error and close the socket on deserialization failure', () => {
      const consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
      mockServerSocket.end = mock(() => {});

      (mockSerializer.deserialize as jest.Mock).mockImplementation(() => {
        throw new Error('Invalid JSON');
      });

      const malformedPayload = Buffer.from('{ not json }');
      const length = Buffer.alloc(4);
      length.writeUInt32BE(malformedPayload.length, 0);
      const framed = Buffer.concat([length, malformedPayload]);

      socketHandlers.data(mockServerSocket, framed);

      expect(consoleErrorSpy).toHaveBeenCalledWith('[Transport] Error processing received message:', expect.any(Error));
      expect(mockServerSocket.end).toHaveBeenCalled();
      expect(mockActorSystem.deliverRemote).not.toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });

    it('should clear the buffer for a socket when it closes', () => {
      const serialized = (mockSerializer.serialize as jest.Mock)(envelope);
      const length = Buffer.alloc(4);
      length.writeUInt32BE(serialized.length, 0);
      const framed = Buffer.concat([length, serialized]);

      const chunk1 = framed.subarray(0, 10);
      socketHandlers.data(mockServerSocket, chunk1);

      const buffersMap = (transport as any).buffers;
      expect(buffersMap.get(mockServerSocket)).toBeDefined();

      socketHandlers.close(mockServerSocket);
      expect(buffersMap.has(mockServerSocket)).toBe(false);
    });
  });
});
