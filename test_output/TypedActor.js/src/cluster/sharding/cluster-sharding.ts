import { ActorSystem } from '../../core/actor-system';
import { ActorRef } from '../../core/actor-ref';
import { ActorContext } from '../../core/actor-context';
import { Actor } from '../../core/actor';
import { Logger } from '../../utils/logger';
import { ShardCoordinator } from './shard-coordinator';
import { ShardRegion } from './shard-region';

export type ActorProps<T extends Actor = Actor> = { new(context: ActorContext<T>): T };

class ShardingProxyRef<TMessage> extends ActorRef<TMessage> {
  constructor(
    system: ActorSystem,
    typeName: string,
    private readonly coordinatorRef: ActorRef<any>,
    private readonly extractEntityId: (message: TMessage) => string,
    private readonly extractShardId: (entityId: string) => string
  ) {
    super(`/system/sharding/${typeName}-proxy`);
  }

  override tell(message: TMessage): void {
    const entityId = this.extractEntityId(message);
    if (!entityId) {
      Logger.warn(`ShardingProxyRef[${this.path}]: Message has no entity ID, dropping message.`);
      return;
    }
    const shardId = this.extractShardId(entityId);

    this.coordinatorRef.tell({
      type: 'ShardEnvelope',
      typeName: this.typeName,
      shardId: shardId,
      entityId: entityId,
      message: message,
    });
  }

  override async ask<TReply>(message: TMessage, timeoutMs?: number): Promise<TReply> {
    const entityId = this.extractEntityId(message);
    if (!entityId) {
      return Promise.reject(new Error(`ShardingProxyRef[${this.path}]: Message has no entity ID for ask.`));
    }
    const shardId = this.extractShardId(entityId);

    return this.coordinatorRef.ask({
      type: 'ShardEnvelopeAndAsk',
      typeName: this.typeName,
      shardId: shardId,
      entityId: entityId,
      message: message,
    }, timeoutMs);
  }
}

export class ClusterSharding {
  private static _instances = new Map<ActorSystem, ClusterSharding>();

  private readonly _system: ActorSystem;
  private readonly _shardingProxies = new Map<string, ActorRef<any>>();
  private readonly _localShardRegions = new Map<string, ActorRef<any>>();
  private _coordinatorRef: ActorRef<any> | null = null;

  private constructor(system: ActorSystem) {
    this._system = system;
  }

  static get(system: ActorSystem): ClusterSharding {
    if (!ClusterSharding._instances.has(system)) {
      const instance = new ClusterSharding(system);
      ClusterSharding._instances.set(system, instance);
    }
    return ClusterSharding._instances.get(system)!;
  }

  async init<TMessage, TEntity extends Actor>(
    typeName: string,
    entityProps: ActorProps<TEntity>,
    extractEntityId: (message: TMessage) => string,
    extractShardId: (entityId: string) => string = (id) => String(id.charCodeAt(0) % 10)
  ): Promise<ActorRef<TMessage>> {
    if (this._shardingProxies.has(typeName)) {
      return this._shardingProxies.get(typeName)! as ActorRef<TMessage>;
    }

    if (!this._coordinatorRef) {
      this._coordinatorRef = this._system.spawn(ShardCoordinator as ActorProps<ShardCoordinator>, 'shardCoordinator');
    }

    const localShardRegionRef = this._system.spawn(
      ShardRegion.props(typeName, entityProps, this._coordinatorRef, extractEntityId, extractShardId),
      `shardRegion-${typeName}-${this._system.name.replace(/[^a-zA-Z0-9]/g, '_')}`
    );
    this._localShardRegions.set(typeName, localShardRegionRef);

    const shardingProxyRef = new ShardingProxyRef(
      this._system,
      typeName,
      this._coordinatorRef,
      extractEntityId,
      extractShardId
    );
    this._shardingProxies.set(typeName, shardingProxyRef);

    return shardingProxyRef;
  }
}
