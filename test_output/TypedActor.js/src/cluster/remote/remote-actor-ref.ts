import { ActorRef } from '../../core/actor-ref';
import { ActorSystem } from '../../core/actor-system';
import { Serializer } from './serialization';
import { Logger } from '../../utils/logger';

export class RemoteActorRef<T> extends ActorRef<T> {
  public readonly address: string;
  private readonly system: ActorSystem;
  private readonly serializer: Serializer;
  private readonly logger = Logger.create('RemoteActorRef');

  constructor(address: string, system: ActorSystem) {
    super();
    this.address = address;
    this.system = system;
    this.serializer = new Serializer();
  }

  public tell(message: T): void {
    try {
      const { host, port, actorPath } = this.parseRemoteAddress(this.address);
      if (!host || !port || !actorPath) {
        this.logger.error(`Invalid remote actor address format for telling: ${this.address}`);
        return;
      }

      const serializedMessage = this.serializer.serialize(message);

      // Delegate to the ActorSystem for actual network transport.
      // Assumes ActorSystem provides methods to send serialized messages to remote addresses.
      this.system.sendRemoteMessage(this.address, serializedMessage);
    } catch (error) {
      this.logger.error(`Error telling message to remote actor ${this.address}: ${error}`);
    }
  }

  public ask<U>(message: any, timeout?: number): Promise<U> {
    return new Promise<U>(async (resolve, reject) => {
      try {
        const { host, port, actorPath } = this.parseRemoteAddress(this.address);
        if (!host || !port || !actorPath) {
          reject(new Error(`Invalid remote actor address format for asking: ${this.address}`));
          return;
        }

        const serializedMessage = this.serializer.serialize(message);

        // Assumes ActorSystem provides methods for request-response communication.
        const responseBuffer = await this.system.askRemoteMessage(this.address, serializedMessage, timeout);

        if (responseBuffer) {
          const deserializedResponse = this.serializer.deserialize(responseBuffer);
          resolve(deserializedResponse as U);
        } else {
          reject(new Error(`Remote actor ${this.address} did not respond within timeout or sent empty response.`));
        }
      } catch (error) {
        this.logger.error(`Error asking message to remote actor ${this.address}: ${error}`);
        reject(error);
      }
    });
  }

  private parseRemoteAddress(fullAddress: string): { protocol?: string; systemName?: string; host?: string; port?: number; actorPath?: string } {
    const regex = /^(?<protocol>[a-zA-Z]+):\/\/(?<systemName>[a-zA-Z0-9_-]+)@(?<host>[a-zA-Z0-9.-]+):(?<port>\d+)(?<actorPath>\/.*)$/;
    const match = fullAddress.match(regex);

    if (match && match.groups) {
      return {
        protocol: match.groups.protocol,
        systemName: match.groups.systemName,
        host: match.groups.host,
        port: parseInt(match.groups.port, 10),
        actorPath: match.groups.actorPath,
      };
    }
    return {};
  }
}
