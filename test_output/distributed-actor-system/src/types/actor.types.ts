import { ActorRef } from '../core/actor-ref';
import { ActorSystem } from '../core/actor-system';
import { Actor } from '../core/actor';

export interface ActorAddress {
  protocol: string;
  system: string;
  host?: string;
  port?: number;
  path: string;
}

export interface ActorContext {
  self: ActorRef<any>;
  parent: ActorRef<any>;
  system: ActorSystem;
  children: Set<ActorRef<any>>;
}

export interface ActorProps {
  actorClass: new (...args: any[]) => Actor<any>;
  args?: any[];
}
