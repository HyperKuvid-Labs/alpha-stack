import { ActorAddress } from '../types/actor.types';
import { ActorSystem } from '../core/actor-system';
import { Serializer } from './serialization';
import { AnyMessage } from '../types/message.types';

export interface RemoteEnvelope {
  recipient: ActorAddress;
  sender?: ActorAddress;
  payload: AnyMessage;
  correlationId?: string;
  messageTypeName?: string;
}

export class Transport {
  private readonly system: ActorSystem;
  private readonly serializer: Serializer;
  private readonly host: string;
  private readonly port: number;
  private server: Bun.Server | null = null;
  private incomingBuffer = new Map<Bun.ServerSocket, Buffer>();

  constructor(system: ActorSystem, serializer: Serializer, host: string, port: number) {
    this.system = system;
    this.serializer = serializer;
    this.host = host;
    this.port = port;
  }

  public async start(): Promise<void> {
    if (this.server) {
      return;
    }

    this.server = Bun.listen({
      hostname: this.host,
      port: this.port,
      socket: {
        data: this.handleIncomingData.bind(this),
        open: (socket) => {},
        close: (socket) => {
          this.incomingBuffer.delete(socket);
        },
        error: (socket, error) => {},
        drain: (socket) => {},
      },
    });
  }

  public async stop(): Promise<void> {
    if (this.server) {
      this.server.stop();
      this.server = null;
    }
  }

  public async send(recipientAddress: ActorAddress, payload: AnyMessage, sender?: ActorAddress, correlationId?: string): Promise<void> {
    const envelope: RemoteEnvelope = {
      recipient: recipientAddress,
      sender: sender,
      payload: payload,
      correlationId: correlationId,
      messageTypeName: payload.constructor.name,
    };

    try {
      const serializedEnvelope = this.serializer.serialize(envelope);

      const lengthBuffer = Buffer.alloc(4);
      lengthBuffer.writeUInt32BE(serializedEnvelope.length, 0);

      const clientSocket = await Bun.connect({
        hostname: recipientAddress.host,
        port: recipientAddress.port,
      });

      clientSocket.write(lengthBuffer);
      clientSocket.write(serializedEnvelope);
      clientSocket.end();

    } catch (error) {}
  }

  private handleIncomingData(socket: Bun.ServerSocket, data: Buffer): void {
    let currentBuffer = this.incomingBuffer.get(socket) || Buffer.alloc(0);
    currentBuffer = Buffer.concat([currentBuffer, data]);

    while (currentBuffer.length >= 4) {
      const messageLength = currentBuffer.readUInt32BE(0);

      if (currentBuffer.length >= 4 + messageLength) {
        const messageBuffer = currentBuffer.subarray(4, 4 + messageLength);
        this.processReceivedMessage(messageBuffer);
        currentBuffer = currentBuffer.subarray(4 + messageLength);
      } else {
        break;
      }
    }
    this.incomingBuffer.set(socket, currentBuffer);
  }

  private processReceivedMessage(buffer: Buffer): void {
    try {
      const envelope: RemoteEnvelope = this.serializer.deserialize(buffer);

      if (!envelope || !envelope.recipient || !envelope.payload) {
        return;
      }

      if (envelope.recipient.system !== this.system.name || envelope.recipient.host !== this.host || envelope.recipient.port !== this.port) {
          return;
      }

      this.system.deliverRemoteMessage(envelope);

    } catch (error) {}
  }
}
