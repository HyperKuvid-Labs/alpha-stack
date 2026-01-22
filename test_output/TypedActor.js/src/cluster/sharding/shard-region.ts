import { Actor, ActorProps } from '../../core/actor';
import { ActorRef } from '../../core/actor-ref';
import { ActorContext } from '../../core/actor-context';
import { handle } from '../../decorators/handle-message';
import { Logger } from '../../utils/logger';
import { PoisonPill } from '../../types/messages';

export class ShardEnvelope<TMessage = any> {
  constructor(
    public readonly entityId: string,
    public readonly shardId: string,
    public readonly message: TMessage
  ) {}
}

export class RegisterShardRegion {
  constructor(public readonly typeName: string) {}
}

export class ShardRegionRegistered {
  constructor(public readonly typeName: string) {}
}

export class GetShardHome {
  constructor(public readonly typeName: string, public readonly shardId: string) {}
}

export class ShardHomeAllocated {
  constructor(public readonly typeName: string, public readonly shardId: string, public readonly regionRef: ActorRef<any>) {}
}

export class HandOff {
  constructor(public readonly shardId: string) {}
}

export class HandOffComplete {
  constructor(public readonly shardId: string) {}
}

export class PassivateEntity {
  constructor(public readonly entityId: string) {}
}

type ShardingManagementMessage =
  | RegisterShardRegion
  | ShardRegionRegistered
  | GetShardHome
  | ShardHomeAllocated
  | HandOff
  | HandOffComplete
  | PassivateEntity;

export interface ShardRegionProps<TEntityMessage = any> {
  typeName: string;
  entityProps: ActorProps;
  extractEntityId: (message: any) => string | undefined;
  extractShardId: (message: any) => string | undefined;
  coordinatorRef: ActorRef<any>;
}

class Shard extends Actor<ShardEnvelope<any> | PassivateEntity> {
    private entities: Map<string, ActorRef<any>> = new Map();
    private readonly entityProps: ActorProps;
    private readonly typeName: string;
    private readonly shardId: string;

    constructor(
        context: ActorContext<ShardEnvelope<any> | PassivateEntity>,
        typeName: string,
        shardId: string,
        entityProps: ActorProps
    ) {
        super(context);
        this.typeName = typeName;
        this.shardId = shardId;
        this.entityProps = entityProps;
    }

    @handle(ShardEnvelope)
    private async onShardEnvelope(envelope: ShardEnvelope<any>): Promise<void> {
        const { entityId, message } = envelope;
        let entityRef = this.entities.get(entityId);

        if (!entityRef) {
            Logger.info(`[${this.typeName}][Shard:${this.shardId}] Spawning entity [${entityId}]`);
            entityRef = this.context.spawn(this.entityProps, entityId);
            this.entities.set(entityId, entityRef);
        }
        entityRef.tell(message);
    }

    @handle(PassivateEntity)
    private async onPassivateEntity(message: PassivateEntity): Promise<void> {
        const { entityId } = message;
        const entityRef = this.entities.get(entityId);
        if (entityRef) {
            Logger.info(`[${this.typeName}][Shard:${this.shardId}] Passivating entity [${entityId}]. Sending PoisonPill.`);
            entityRef.tell(new PoisonPill());
            this.entities.delete(entityId);
        } else {
            Logger.warn(`[${this.typeName}][Shard:${this.shardId}] Received PassivateEntity for unknown entity [${entityId}].`);
        }
    }

    postStop(): void {
        Logger.info(`[${this.typeName}][Shard:${this.shardId}] Stopping. Stopping all active entities.`);
        for (const entityRef of this.entities.values()) {
            entityRef.tell(new PoisonPill());
        }
        this.entities.clear();
    }
}

export class ShardRegion<TEntityMessage = any> extends Actor<TEntityMessage | ShardEnvelope<TEntityMessage> | ShardingManagementMessage> {
  private readonly typeName: string;
  private readonly entityProps: ActorProps;
  private readonly extractEntityId: (message: any) => string | undefined;
  private readonly extractShardId: (message: any) => string | undefined;
  private readonly coordinatorRef: ActorRef<any>;

  private readonly shards: Map<string, ActorRef<ShardEnvelope<any> | PassivateEntity>> = new Map();
  private readonly pendingShardAllocations: Map<string, ShardEnvelope<TEntityMessage>[]> = new Map();

  constructor(
    context: ActorContext<TEntityMessage | ShardEnvelope<TEntityMessage> | ShardingManagementMessage>,
    props: ShardRegionProps<TEntityMessage>
  ) {
    super(context);
    this.typeName = props.typeName;
    this.entityProps = props.entityProps;
    this.extractEntityId = props.extractEntityId;
    this.extractShardId = props.extractShardId;
    this.coordinatorRef = props.coordinatorRef;
  }

  async preStart(): Promise<void> {
    Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Starting. Registering with ShardCoordinator.`);
    this.coordinatorRef.tell(new RegisterShardRegion(this.typeName));
  }

  postStop(): void {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Stopping. Stopping all active shards.`);
      for (const shardRef of this.shards.values()) {
          this.context.stop(shardRef);
      }
      this.shards.clear();
      this.pendingShardAllocations.clear();
  }

  @handle(ShardRegionRegistered)
  private onShardRegionRegistered(message: ShardRegionRegistered): void {
    if (message.typeName === this.typeName) {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Successfully registered with ShardCoordinator.`);
    }
  }

  @handle(ShardHomeAllocated)
  private async onShardHomeAllocated(message: ShardHomeAllocated): Promise<void> {
    if (message.typeName !== this.typeName) {
      Logger.warn(`[${this.typeName}][ShardRegion:${this.context.self.path}] Received ShardHomeAllocated for unknown typeName: ${message.typeName}`);
      return;
    }

    const { shardId, regionRef } = message;

    if (regionRef.path === this.context.self.path) {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Allocated as home for shard [${shardId}]`);

      if (!this.shards.has(shardId)) {
        Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Spawning shard actor [${shardId}]`);
        const shardActorRef = this.context.spawn(
          ActorProps.create(Shard, this.typeName, shardId, this.entityProps),
          `shard-${shardId}`
        );
        this.shards.set(shardId, shardActorRef as ActorRef<ShardEnvelope<any> | PassivateEntity>);

        const pendingMessages = this.pendingShardAllocations.get(shardId);
        if (pendingMessages) {
          Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Forwarding ${pendingMessages.length} pending messages for shard [${shardId}]`);
          for (const envelope of pendingMessages) {
            shardActorRef.tell(envelope);
          }
          this.pendingShardAllocations.delete(shardId);
        }
      } else {
        Logger.warn(`[${this.typeName}][ShardRegion:${this.context.self.path}] Received ShardHomeAllocated for already existing shard [${shardId}].`);
      }
    } else {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Shard [${shardId}] is homed on remote region: ${regionRef.path}`);

      const pendingMessages = this.pendingShardAllocations.get(shardId);
      if (pendingMessages) {
        Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Forwarding ${pendingMessages.length} pending messages to remote region ${regionRef.path} for shard [${shardId}]`);
        for (const envelope of pendingMessages) {
          regionRef.tell(envelope);
        }
        this.pendingShardAllocations.delete(shardId);
      }
    }
  }

  @handle(HandOff)
  private async onHandOff(message: HandOff): Promise<void> {
    const { shardId } = message;
    const shardRef = this.shards.get(shardId);

    if (shardRef) {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Received HandOff for shard [${shardId}]. Stopping shard.`);
      this.context.stop(shardRef);
      this.shards.delete(shardId);
      this.coordinatorRef.tell(new HandOffComplete(shardId));
    } else {
      Logger.warn(`[${this.typeName}][ShardRegion:${this.context.self.path}] Received HandOff for unknown or already stopped shard [${shardId}].`);
      this.coordinatorRef.tell(new HandOffComplete(shardId));
    }
  }

  @handle(PassivateEntity)
  private async onPassivateEntityRegion(message: PassivateEntity): Promise<void> {
    const { entityId } = message;
    const shardId = this.extractShardId(message);

    if (!shardId) {
      Logger.warn(`[${this.typeName}][ShardRegion:${this.context.self.path}] Cannot extract shardId from PassivateEntity message for entity [${entityId}]. Dropping.`);
      return;
    }

    const shardRef = this.shards.get(shardId);
    if (shardRef) {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Forwarding PassivateEntity for [${entityId}] to shard [${shardId}].`);
      shardRef.tell(message);
    } else {
      Logger.warn(`[${this.typeName}][ShardRegion:${this.context.self.path}] Cannot passivate entity [${entityId}]: Shard [${shardId}] not found in this region. Requesting home from coordinator.`);
      
      let pendingMessages = this.pendingShardAllocations.get(shardId);
      if (!pendingMessages) {
        pendingMessages = [];
        this.pendingShardAllocations.set(shardId, pendingMessages);
      }
      pendingMessages.push(new ShardEnvelope(entityId, shardId, message));
      this.coordinatorRef.tell(new GetShardHome(this.typeName, shardId));
    }
  }

  async receive(message: TEntityMessage | ShardEnvelope<TEntityMessage> | any): Promise<void> {
    if (message instanceof ShardEnvelope) {
        await this.handleEntityMessage(message.entityId, message.shardId, message.message);
        return;
    }

    const entityId = this.extractEntityId(message);
    const shardId = this.extractShardId(message);

    if (!entityId || !shardId) {
        Logger.warn(`[${this.typeName}][ShardRegion:${this.context.self.path}] Cannot extract entityId or shardId from message. Dropping message.`);
        return;
    }

    await this.handleEntityMessage(entityId, shardId, message);
  }

  private async handleEntityMessage(entityId: string, shardId: string, message: TEntityMessage): Promise<void> {
    const envelope = new ShardEnvelope(entityId, shardId, message);
    const shardRef = this.shards.get(shardId);

    if (shardRef) {
      shardRef.tell(envelope);
    } else {
      Logger.info(`[${this.typeName}][ShardRegion:${this.context.self.path}] Shard [${shardId}] not active. Requesting home from coordinator.`);
      
      let pendingMessages = this.pendingShardAllocations.get(shardId);
      if (!pendingMessages) {
        pendingMessages = [];
        this.pendingShardAllocations.set(shardId, pendingMessages);
      }
      pendingMessages.push(envelope);

      this.coordinatorRef.tell(new GetShardHome(this.typeName, shardId));
    }
  }
}
