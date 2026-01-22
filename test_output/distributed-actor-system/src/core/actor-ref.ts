import { ActorAddress } from '../types/actor.types';
import { ActorSystem } from './actor-system';

// Define ActorPath as string from ActorAddress.path
type ActorPath = string;

// Define Address as an alias for ActorAddress if not explicitly defined elsewhere.
type Address = ActorAddress;

// Define Nobody as a type for a special ActorRef that cannot receive messages.
type Nobody = ActorRef<never>;

export class ActorRef<T> {
  public readonly address: ActorAddress;
  public readonly path: ActorPath;
  private readonly _system: ActorSystem;

  constructor(address: ActorAddress, system: ActorSystem) {
    this.address = address;
    this.path = address.path;
    this._system = system;
  }

  tell(message: T, sender?: ActorRef<any>): void {
    this._system.sendMessage(this.address, message, sender);
  }

  ask<R>(message: T, timeoutMs?: number): Promise<R> {
    return this._system.requestMessage(this.address, message, timeoutMs);
  }
}

// Re-export the types
export { ActorAddress, Address, Nobody };
```
```tool_code
{"log_change_response": {"success": true}}
