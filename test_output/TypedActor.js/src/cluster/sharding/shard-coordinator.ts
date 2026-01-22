import { Actor, ActorContext, ActorRef } from '../../core/actor';
import { handle } from '../../decorators/handle-message';
import { PersistentActor } from '../../persistence/persistent-actor';
import { Logger } from '../../utils/logger';
import { ActorSystem } from '../../core/actor-system';
import { MemberUp, MemberDown, UnreachableMember } from '../membership/cluster-events';

export class RegisterShardRegion {
    constructor(public readonly regionRef: ActorRef<any>, public readonly regionAddress: string) {}
}

export class RequestShardAllocation {
    constructor(public readonly shardId: string, public readonly entityId: string, public readonly senderRegion: ActorRef<any>) {}
}

export class ShardAllocated {
    constructor(public readonly shardId: string, public readonly regionRef: ActorRef<any>) {}
}

export class ShardTerminated {
    constructor(public readonly shardId: string, public readonly regionRef: ActorRef<any>) {}
}

class ShardRegionRegisteredEvent {
    constructor(public readonly regionRefPath: string, public readonly regionAddress: string) {}
}

class ShardRegionRemovedEvent {
    constructor(public readonly regionRefPath: string) {}
}

class ShardAllocatedEvent {
    constructor(public readonly shardId: string, public readonly regionRefPath: string) {}
}

class ShardTerminatedEvent {
    constructor(public readonly shardId: string, public readonly regionRefPath: string) {}
}

type CoordinatorEvent = ShardRegionRegisteredEvent | ShardRegionRemovedEvent | ShardAllocatedEvent | ShardTerminatedEvent;

interface ShardCoordinatorState {
    shardAllocations: Map<string, string>;
    regionToShards: Map<string, Set<string>>;
    registeredRegions: Set<ActorRef<any>>;
    regionRoundRobinIndex: number;
}

export class ShardCoordinator extends PersistentActor<CoordinatorEvent, ShardCoordinatorState> {
    readonly persistenceId: string = "shard-coordinator";

    protected state: ShardCoordinatorState = {
        shardAllocations: new Map(),
        regionToShards: new Map(),
        registeredRegions: new Set(),
        regionRoundRobinIndex: 0,
    };

    private readonly log = Logger.forActor(this);
    private readonly system: ActorSystem;

    constructor(context: ActorContext<any>) {
        super(context);
        this.system = context.system;
    }

    preStart(): void {
        super.preStart();
        this.log.info("ShardCoordinator starting up.");
        this.system.eventStream.subscribe(MemberUp, this.onMemberUp.bind(this));
        this.system.eventStream.subscribe(MemberDown, this.onMemberDown.bind(this));
        this.system.eventStream.subscribe(UnreachableMember, this.onUnreachableMember.bind(this));
    }

    postStop(): void {
        this.log.info("ShardCoordinator shutting down.");
        this.system.eventStream.unsubscribe(MemberUp, this.onMemberUp.bind(this));
        this.system.eventStream.unsubscribe(MemberDown, this.onMemberDown.bind(this));
        this.system.eventStream.unsubscribe(UnreachableMember, this.onUnreachableMember.bind(this));
        super.postStop();
    }

    receiveRecover(event: CoordinatorEvent): void {
        if (event instanceof ShardAllocatedEvent) {
            this.state.shardAllocations.set(event.shardId, event.regionRefPath);
            if (!this.state.regionToShards.has(event.regionRefPath)) {
                this.state.regionToShards.set(event.regionRefPath, new Set());
            }
            this.state.regionToShards.get(event.regionRefPath)?.add(event.shardId);
        } else if (event instanceof ShardTerminatedEvent) {
            this.state.shardAllocations.delete(event.shardId);
            this.state.regionToShards.get(event.regionRefPath)?.delete(event.shardId);
            if (this.state.regionToShards.get(event.regionRefPath)?.size === 0) {
                this.state.regionToShards.delete(event.regionRefPath);
            }
        }
    }

    @handle(RegisterShardRegion)
    private async onRegisterShardRegion(message: RegisterShardRegion): Promise<void> {
        const { regionRef, regionAddress } = message;

        if (!Array.from(this.state.registeredRegions).some(ref => ref.equals(regionRef))) {
            await this.persist(new ShardRegionRegisteredEvent(regionRef.path, regionAddress));
            this.state.registeredRegions.add(regionRef);
            this.log.info(`ShardRegion ${regionRef.path} (${regionAddress}) registered.`);
        } else {
            this.log.warn(`ShardRegion ${regionRef.path} (${regionAddress}) already registered.`);
        }
    }

    @handle(RequestShardAllocation)
    private async onRequestShardAllocation(message: RequestShardAllocation): Promise<void> {
        const { shardId, senderRegion } = message;

        const existingOwnerPath = this.state.shardAllocations.get(shardId);
        let existingOwnerRef: ActorRef<any> | undefined;

        if (existingOwnerPath) {
            existingOwnerRef = Array.from(this.state.registeredRegions).find(ref => ref.path === existingOwnerPath);
            if (existingOwnerRef) {
                this.log.info(`Shard ${shardId} already allocated to ${existingOwnerRef.path}. Informing ${senderRegion.path}.`);
                senderRegion.tell(new ShardAllocated(shardId, existingOwnerRef));
                return;
            } else {
                this.log.warn(`Shard ${shardId} was allocated to ${existingOwnerPath}, but that region is not currently registered. Reallocating.`);
                this.state.shardAllocations.delete(shardId);
                this.state.regionToShards.get(existingOwnerPath)?.delete(shardId);
            }
        }

        const targetRegion = this.selectShardRegionForAllocation();

        if (targetRegion) {
            await this.persist(new ShardAllocatedEvent(shardId, targetRegion.path));
            this.state.shardAllocations.set(shardId, targetRegion.path);

            if (!this.state.regionToShards.has(targetRegion.path)) {
                this.state.regionToShards.set(targetRegion.path, new Set());
            }
            this.state.regionToShards.get(targetRegion.path)?.add(shardId);

            this.log.info(`Allocated shard ${shardId} to region ${targetRegion.path}. Informing ${senderRegion.path}.`);
            senderRegion.tell(new ShardAllocated(shardId, targetRegion));
        } else {
            this.log.error(`No ShardRegions available to allocate shard ${shardId}.`);
        }
    }

    @handle(ShardTerminated)
    private async onShardTerminated(message: ShardTerminated): Promise<void> {
        const { shardId, regionRef } = message;

        const currentOwnerPath = this.state.shardAllocations.get(shardId);
        if (currentOwnerPath === regionRef.path) {
            this.log.info(`Shard ${shardId} terminated by its owner region ${regionRef.path}.`);
            await this.persist(new ShardTerminatedEvent(shardId, regionRef.path));

            this.state.shardAllocations.delete(shardId);
            this.state.regionToShards.get(regionRef.path)?.delete(shardId);
            if (this.state.regionToShards.get(regionRef.path)?.size === 0) {
                this.state.regionToShards.delete(regionRef.path);
            }
        } else if (currentOwnerPath) {
            this.log.warn(`Received ShardTerminated for ${shardId} from ${regionRef.path}, but current owner is ${currentOwnerPath}. Ignoring.`);
        } else {
            this.log.warn(`Received ShardTerminated for ${shardId} from ${regionRef.path}, but shard was not allocated. Ignoring.`);
        }
    }

    private selectShardRegionForAllocation(): ActorRef<any> | undefined {
        const availableRegionsArray = Array.from(this.state.registeredRegions);

        if (availableRegionsArray.length === 0) {
            return undefined;
        }

        const targetRegion = availableRegionsArray[this.state.regionRoundRobinIndex];
        this.state.regionRoundRobinIndex = (this.state.regionRoundRobinIndex + 1) % availableRegionsArray.length;

        return targetRegion;
    }

    private onMemberUp(event: MemberUp): void {
        this.log.info(`Cluster member UP: ${event.memberAddress}`);
    }

    private async onMemberDown(event: MemberDown): Promise<void> {
        this.log.warn(`Cluster member DOWN: ${event.memberAddress}. Shards on this node might become unassigned.`);
        const regionsToRemove: ActorRef<any>[] = [];
        for (const regionRef of this.state.registeredRegions) {
            if (regionRef.path.includes(event.memberAddress)) {
                regionsToRemove.push(regionRef);
            }
        }
        for (const regionRef of regionsToRemove) {
            await this.removeShardRegion(regionRef);
        }
    }

    private async onUnreachableMember(event: UnreachableMember): Promise<void> {
        this.log.warn(`Cluster member UNREACHABLE: ${event.memberAddress}. Shards on this node might become temporarily unavailable.`);
        const regionsToRemove: ActorRef<any>[] = [];
        for (const regionRef of this.state.registeredRegions) {
            if (regionRef.path.includes(event.memberAddress)) {
                regionsToRemove.push(regionRef);
            }
        }
        for (const regionRef of regionsToRemove) {
            await this.removeShardRegion(regionRef);
        }
    }

    private async removeShardRegion(regionRef: ActorRef<any>): Promise<void> {
        if (this.state.registeredRegions.delete(regionRef)) {
            this.log.info(`ShardRegion ${regionRef.path} removed.`);
            await this.persist(new ShardRegionRemovedEvent(regionRef.path));

            const shardsOwnedByRegion = this.state.regionToShards.get(regionRef.path);
            if (shardsOwnedByRegion) {
                for (const shardId of shardsOwnedByRegion) {
                    this.state.shardAllocations.delete(shardId);
                    this.log.warn(`Shard ${shardId} unassigned due to region ${regionRef.path} removal.`);
                }
                this.state.regionToShards.delete(regionRef.path);
            }
        }
    }
}
