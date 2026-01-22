import { ActorRef } from './actor-ref';
import { ActorSystem, ActorProps } from './actor-system';

interface InternalActorSystem {
  _spawnChild<T>(parent: ActorRef<any>, props: ActorProps, name?: string): ActorRef<T>;
  _stopActor(actorRef: ActorRef<any>): void;
}

export class ActorContext<T> {
  public readonly self: ActorRef<T>;
  public readonly parent: ActorRef<any>;
  public readonly system: ActorSystem;

  constructor(self: ActorRef<T>, parent: ActorRef<any>, system: ActorSystem) {
    this.self = self;
    this.parent = parent;
    this.system = system;
  }

  public spawn(props: ActorProps, name?: string): ActorRef<any> {
    return (this.system as unknown as InternalActorSystem)._spawnChild(this.self, props, name);
  }

  public stop(child: ActorRef<any>): void {
    (this.system as unknown as InternalActorSystem)._stopActor(child);
  }
}
