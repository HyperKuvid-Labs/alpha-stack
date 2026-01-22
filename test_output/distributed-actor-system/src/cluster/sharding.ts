import { ActorSystem } from '../core/actor-system';
import { ActorRef } from '../core/actor-ref';
import { Actor } from '../core/actor';
import { Receive } from '../core/decorators';
import { ActorAddress, ShardingOptions, ClusterMember } from '../types/cluster.types';
import { ActorContext, ActorProps } from '../types/actor.types';
import { NodeManager } from './node-manager';

class ShardRegionProxyMessage<T> {
  constructor(public entityId: string, public message: T) {}
}

export class ShardRegionActor<T extends object> extends Actor<ShardRegionProxyMessage<T>> {
  private entities: Map<string, ActorRef<T>> = new Map();
  private typeName: string;
  private entityProps: ActorProps;

  constructor(context: ActorContext, typeName: string, entityProps: ActorProps) {
    super(context);
    this.typeName = typeName;
    this.entityProps = entityProps;
  }

  preStart() {}

  @Receive(ShardRegionProxyMessage)
  private handleProxyMessage(msg: ShardRegionProxyMessage<T>) {
    let entityRef = this.entities.get(msg.entityId);
    if (!entityRef) {
      entityRef = this.context.actorOf({
        ...this.entityProps,
        args: [msg.entityId, ...(this.entityProps.args || [])]
      }, msg.entityId);
      this.entities.set(msg.entityId, entityRef);
    }
    entityRef.tell(msg.message, this.context.self);
  }

  postStop() {
    this.entities.clear();
  }
}

export class ShardRouter {
  private numberOfShards: number;
  private nodeManager: NodeManager;
  private shardToNodeMapping: Map<number, ActorAddress> = new Map();
  private readonly selfAddress: ActorAddress;

  constructor(numberOfShards: number, nodeManager: NodeManager, selfAddress: ActorAddress) {
    this.numberOfShards = numberOfShards;
    this.nodeManager = nodeManager;
    this.selfAddress = selfAddress;
    this.rebuildShardMapping();
  }

  private hashString(s: string): number {
    let hash = 0;
    for (let i = 0; i < s.length; i++) {
      const char = s.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash |= 0;
    }
    return Math.abs(hash);
  }

  getShardId(entityId: string): number {
    return this.hashString(entityId) % this.numberOfShards;
  }

  rebuildShardMapping() {
    const members = this.nodeManager.getMembers();
    this.shardToNodeMapping.clear();

    if (members.length === 0) {
      return;
    }

    const sortedMembers = [...members].sort((a, b) => {
      const addrA = `${a.address.protocol}://${a.address.system}@${a.address.host}:${a.address.port}`;
      const addrB = `${b.address.protocol}://${b.address.system}@${b.address.host}:${b.address.port}`;
      return addrA.localeCompare(addrB);
    });

    for (let i = 0; i < this.numberOfShards; i++) {
      const member = sortedMembers[i % sortedMembers.length];
      this.shardToNodeMapping.set(i, member.address);
    }
  }

  getNodeForShard(shardId: number): ActorAddress | undefined {
    return this.shardToNodeMapping.get(shardId);
  }
}

export class InternalShardedActorRef<T extends object> implements ActorRef<T> {
  public address: ActorAddress;
  private system: ActorSystem;
  private getTargetShardRegionAddress: () => ActorAddress;
  private entityId: string;

  constructor(system: ActorSystem, typeName: string, entityId: string, getTargetShardRegionAddress: () => ActorAddress) {
    this.system = system;
    this.getTargetShardRegionAddress = getTargetShardRegionAddress;
    this.entityId = entityId;
    this.address = {
      protocol: system.address.protocol,
      system: system.address.system,
      host: system.address.host,
      port: system.address.port,
      path: `${system.address.path}/sharded/${typeName}/${entityId}`
    };
  }

  tell(message: T, sender?: ActorRef<any>): void {
    const targetRegionAddress = this.getTargetShardRegionAddress();
    const proxyMessage = new ShardRegionProxyMessage(this.entityId, message);
    const targetRegionRef = this.system.actorRef(targetRegionAddress);
    targetRegionRef.tell(proxyMessage, sender);
  }

  ask<R>(message: T, timeoutMs?: number): Promise<R> {
    const targetRegionAddress = this.getTargetShardRegionAddress();
    const proxyMessage = new ShardRegionProxyMessage(this.entityId, message);
    const targetRegionRef = this.system.actorRef(targetRegionAddress);
    return targetRegionRef.ask<R>(proxyMessage, timeoutMs);
  }
}

export class ClusterSharding {
  private system: ActorSystem;
  private options: ShardingOptions;
  private nodeManager: NodeManager;
  private shardRouter: ShardRouter;
  private localShardRegionRefs: Map<string, ActorRef<any>> = new Map();

  private constructor(system: ActorSystem, options: ShardingOptions, nodeManager: NodeManager) {
    this.system = system;
    this.options = options;
    this.nodeManager = nodeManager;
    this.shardRouter = new ShardRouter(options.numberOfShards, nodeManager, system.address);
  }

  static async init(system: ActorSystem, options: ShardingOptions): Promise<ClusterSharding> {
    const nodeManager = (system as any).nodeManager as NodeManager;
    if (!nodeManager) {
      throw new Error("NodeManager not found on ActorSystem. ClusterSharding requires a NodeManager.");
    }

    const sharding = new ClusterSharding(system, options, nodeManager);
    await sharding.startLocalShardRegions();
    return sharding;
  }

  private async startLocalShardRegions() {
    for (const typeName in this.options.entityActorProps) {
      if (Object.prototype.hasOwnProperty.call(this.options.entityActorProps, typeName)) {
        const entityProps = this.options.entityActorProps[typeName];

        const shardRegionActorName = `sharding-${typeName}-region`;
        const shardRegionRef = this.system.actorOf({
          actorClass: ShardRegionActor as any,
          args: [typeName, entityProps]
        }, shardRegionActorName);
        this.localShardRegionRefs.set(typeName, shardRegionRef);
      }
    }
  }

  entityRefFor<T extends object>(typeName: string, entityId: string): ActorRef<T> {
    if (!this.options.entityActorProps[typeName]) {
      throw new Error(`Sharding for type "${typeName}" is not configured. Add it to ShardingOptions.entityActorProps.`);
    }

    const getTargetShardRegionAddressFn = () => {
        const shardId = this.shardRouter.getShardId(entityId);
        const targetNodeAddress = this.shardRouter.getNodeForShard(shardId);
        if (!targetNodeAddress) {
            throw new Error(`Cannot resolve target node for shard ${shardId} for entityId \'${entityId}\' (type: ${typeName}). No active nodes or shard not assigned.`);
        }
        const shardRegionActorPath = `${targetNodeAddress.path}/user/sharding-${typeName}-region`;
        return {
          protocol: targetNodeAddress.protocol,
          system: targetNodeAddress.system,
          host: targetNodeAddress.host,
          port: targetNodeAddress.port,
          path: shardRegionActorPath,
        };
    };

    return new InternalShardedActorRef<T>(this.system, typeName, entityId, getTargetShardRegionAddressFn);
  }
}
