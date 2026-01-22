import { ActorAddress } from '../types/actor.types';

export class Serializer {
  public serialize(message: object): Buffer {
    let jsonString: string;
    if (message instanceof ActorAddress) {
      jsonString = JSON.stringify({
        _isActorAddress: true,
        protocol: message.protocol,
        system: message.system,
        host: message.host,
        port: message.port,
        path: message.path,
      });
    } else {
      jsonString = JSON.stringify(message);
    }
    return Buffer.from(jsonString, 'utf-8');
  }

  public deserialize(buffer: Buffer): object {
    const jsonString = buffer.toString('utf-8');
    const parsed = JSON.parse(jsonString);

    if (parsed && typeof parsed === 'object' && parsed._isActorAddress && parsed.protocol && parsed.system && parsed.path) {
      const address = new ActorAddress(parsed.protocol, parsed.system, parsed.path, parsed.host, parsed.port);
      return address;
    }
    return parsed;
  }
}
