import { ActorAddress, ActorRef } from '../types/actor.types';
import { Serializer } from './serialization';
import { RemoteTransport } from './transport';

export class RemoteProxy {
  private serializer: Serializer;
  private transport: RemoteTransport;

  constructor(serializer: Serializer, transport: RemoteTransport) {
    this.serializer = serializer;
    this.transport = transport;
  }

  public tell(recipientAddress: ActorAddress, message: any, sender?: ActorRef<any>): void {
    const envelope = {
      type: 'tell',
      recipient: recipientAddress,
      message: message,
      sender: sender ? sender.address : undefined,
    };
    const serializedEnvelope = this.serializer.serialize(envelope);
    this.transport.send(recipientAddress, serializedEnvelope);
  }

  public async ask<R>(recipientAddress: ActorAddress, message: any, timeoutMs?: number, sender?: ActorRef<any>): Promise<R> {
    const correlationId = this.generateCorrelationId();

    const envelope = {
      type: 'ask',
      recipient: recipientAddress,
      message: message,
      sender: sender ? sender.address : undefined,
      correlationId: correlationId,
    };

    const serializedEnvelope = this.serializer.serialize(envelope);

    const responseBuffer = await this.transport.request(recipientAddress, serializedEnvelope, correlationId, timeoutMs);
    const deserializedResponse = this.serializer.deserialize(responseBuffer);
    return deserializedResponse as R;
  }

  private generateCorrelationId(): string {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  }
}
