import { vi, test, expect, describe, beforeEach, afterEach } from 'bun:test';
import { ActorSystem } from '../../core/actor-system';
import { Actor, ActorProps } from '../../core/actor';
import { ActorRef } from '../../core/actor-ref';
import { ActorContext } from '../../core/actor-context';
import { PoisonPill, Terminated } from '../../types/messages';
import {
    ShardRegion,
    Shard,
    ShardEnvelope,
    RegisterShardRegion,
    GetShardHome,
    ShardHomeAllocated,
    PassivateEntity,
    StopEntity,
    HandOff
} from './shard-region';

class TestProbe extends Actor {
    public messages: any[] = [];

    constructor(private probeRef?: ActorRef<any>) {
        super();
    }

    async receive(message: any): Promise<void> {
        this.messages.push(message);
        if (this.probeRef) {
            this.probeRef.tell(message);
        }
    }
}

class TestEntityActor extends Actor {
    private state: number = 0;
    constructor(private readonly entityId: string) {
        super();
    }

    async receive(message: any): Promise<void> {
        if (message.type === 'increment') {
            this.state++;
        }
        if (message.type === 'get_state') {
            this.context.sender?.tell({ entityId: this.entityId, state: this.state });
        }
        if (message instanceof PassivateEntity) {
            this.context.parent.tell(new StopEntity(this.entityId));
        }
    }
}

describe('ShardRegion and Shard', () => {
    let system: ActorSystem;
    let coordinatorProbe: ActorRef<any>;
    let entityProps: (entityId: string) => ActorProps;

    beforeEach(() => {
        system = ActorSystem.create('TestSystem');
        const probeProps = Actor.props(TestProbe);
        coordinatorProbe = system.actorOf(probeProps, 'coordinatorProbe');
        entityProps = (entityId: string) => Actor.props(TestEntityActor, entityId);
    });

    afterEach(async () => {
        await system.shutdown();
    });

    describe('ShardRegion', () => {
        test('should register with the coordinator on preStart', async () => {
            const shardRegionProps = Actor.props(
                ShardRegion,
                'TestType',
                entityProps,
                coordinatorProbe,
                10,
                30,
            );
            const shardRegion = system.actorOf(shardRegionProps, 'testRegion');

            await new Promise(r => setTimeout(r, 50)); // allow time for preStart

            const probeActor = system.getActor(coordinatorProbe.path);
            expect(probeActor).toBeInstanceOf(TestProbe);
            const messages = (probeActor as TestProbe).messages;
            
            expect(messages.length).toBe(1);
            expect(messages[0]).toBeInstanceOf(RegisterShardRegion);
            expect(messages[0].shardRegion).toEqual(shardRegion);
        });

        test('should request shard home for a new entity and buffer messages', async () => {
            const shardRegion = system.actorOf(
                Actor.props(ShardRegion, 'TestType', entityProps, coordinatorProbe, 10, 30),
                'testRegion'
            );

            const message1 = { type: 'increment' };
            const message2 = { type: 'get_state' };

            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', message1));
            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', message2));

            await new Promise(r => setTimeout(r, 50));

            const probeActor = system.getActor(coordinatorProbe.path) as TestProbe;
            expect(probeActor.messages.length).toBe(1);
            expect(probeActor.messages[0]).toBeInstanceOf(GetShardHome);
            expect(probeActor.messages[0].shardId).toBe('shard-1');
        });

        test('should create local shard and deliver buffered messages on ShardHomeAllocated', async () => {
            const regionProps = Actor.props(ShardRegion, 'TestType', entityProps, coordinatorProbe, 10, 30);
            const shardRegion = system.actorOf(regionProps, 'region');

            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));

            await new Promise(r => setTimeout(r, 50)); // Wait for GetShardHome

            // Simulate coordinator response
            shardRegion.tell(new ShardHomeAllocated('shard-1', shardRegion));
            
            await new Promise(r => setTimeout(r, 50)); // Wait for shard and entity creation

            const testProbe = system.actorOf(Actor.props(TestProbe), 'probe');
            
            // Find the entity actor to query its state
            const shardActorRef = await system.actorSelection(shardRegion.path.toString() + '/shard-1');
            const entityActorRef = await system.actorSelection(shardActorRef!.path.toString() + '/entity-1');

            expect(entityActorRef).not.toBeNull();

            entityActorRef!.tell({ type: 'get_state' }, testProbe);
            
            await new Promise(r => setTimeout(r, 50)); // Wait for response

            const probeActor = system.getActor(testProbe.path) as TestProbe;
            expect(probeActor.messages.length).toBe(1);
            expect(probeActor.messages[0]).toEqual({ entityId: 'entity-1', state: 2 });
        });

        test('should forward messages to an existing local shard', async () => {
             const regionProps = Actor.props(ShardRegion, 'TestType', entityProps, coordinatorProbe, 10, 30);
            const shardRegion = system.actorOf(regionProps, 'region');

            // First message to create the shard
            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            shardRegion.tell(new ShardHomeAllocated('shard-1', shardRegion));
            await new Promise(r => setTimeout(r, 50));

            // Second message should be forwarded directly
            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            await new Promise(r => setTimeout(r, 50));

            const testProbe = system.actorOf(Actor.props(TestProbe), 'probe');
            const entityActorRef = await system.actorSelection('akka://TestSystem/user/region/shard-1/entity-1');
            entityActorRef!.tell({ type: 'get_state' }, testProbe);

            await new Promise(r => setTimeout(r, 50));

            const probeActor = system.getActor(testProbe.path) as TestProbe;
            expect(probeActor.messages[0].state).toBe(2);
        });

        test('should handle HandOff by stopping the correct shard', async () => {
            const regionProps = Actor.props(ShardRegion, 'TestType', entityProps, coordinatorProbe, 10, 30);
            const shardRegion = system.actorOf(regionProps, 'region');

            shardRegion.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            shardRegion.tell(new ShardHomeAllocated('shard-1', shardRegion));
            await new Promise(r => setTimeout(r, 50));
            
            const shardActorRef = await system.actorSelection(shardRegion.path.toString() + '/shard-1');
            expect(shardActorRef).not.toBeNull();
            
            const terminationProbe = system.actorOf(Actor.props(TestProbe), 'terminationProbe');
            system.watch(shardActorRef!, terminationProbe);

            shardRegion.tell(new HandOff('shard-1'));
            await new Promise(r => setTimeout(r, 100));
            
            const probeActor = system.getActor(terminationProbe.path) as TestProbe;
            expect(probeActor.messages.length).toBe(1);
            expect(probeActor.messages[0]).toBeInstanceOf(Terminated);
            expect(probeActor.messages[0].actorRef.path.name).toBe('shard-1');
        });
    });

    describe('Shard', () => {
        test('should create an entity actor on first message', async () => {
            const shardProps = Actor.props(Shard, 'shard-1', entityProps, 30);
            const shard = system.actorOf(shardProps, 'shard-1');

            shard.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            await new Promise(r => setTimeout(r, 50));
            
            const entityRef = await system.actorSelection('akka://TestSystem/user/shard-1/entity-1');
            expect(entityRef).not.toBeNull();
        });

        test('should forward messages to existing entity actor', async () => {
            const shard = system.actorOf(Actor.props(Shard, 'shard-1', entityProps, 30), 'shard-1');
            const testProbe = system.actorOf(Actor.props(TestProbe), 'probe');

            shard.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            shard.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            await new Promise(r => setTimeout(r, 50));
            
            shard.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'get_state' }, testProbe));
            await new Promise(r => setTimeout(r, 50));

            const probeActor = system.getActor(testProbe.path) as TestProbe;
            expect(probeActor.messages.length).toBe(1);
            expect(probeActor.messages[0].state).toBe(2);
        });

        test('should stop an entity when receiving StopEntity', async () => {
            const shard = system.actorOf(Actor.props(Shard, 'shard-1', entityProps, 30), 'shard-1');
            
            shard.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            await new Promise(r => setTimeout(r, 50));

            const entityRef = await system.actorSelection('akka://TestSystem/user/shard-1/entity-1');
            expect(entityRef).not.toBeNull();

            const terminationProbe = system.actorOf(Actor.props(TestProbe), 'terminationProbe');
            system.watch(entityRef!, terminationProbe);

            shard.tell(new StopEntity('entity-1'));
            await new Promise(r => setTimeout(r, 50));

            const probeActor = system.getActor(terminationProbe.path) as TestProbe;
            expect(probeActor.messages.length).toBe(1);
            expect(probeActor.messages[0]).toBeInstanceOf(Terminated);
            expect(probeActor.messages[0].actorRef.path.name).toBe('entity-1');
        });

        test('should stop all entities and itself on HandOff', async () => {
            const shard = system.actorOf(Actor.props(Shard, 'shard-1', entityProps, 30), 'shard-1');
            const terminationProbe = system.actorOf(Actor.props(TestProbe), 'terminationProbe');

            shard.tell(new ShardEnvelope('shard-1', 'entity-1', {}));
            shard.tell(new ShardEnvelope('shard-1', 'entity-2', {}));
            await new Promise(r => setTimeout(r, 50));

            const entity1Ref = await system.actorSelection('akka://TestSystem/user/shard-1/entity-1');
            const entity2Ref = await system.actorSelection('akka://TestSystem/user/shard-1/entity-2');
            
            system.watch(entity1Ref!, terminationProbe);
            system.watch(entity2Ref!, terminationProbe);
            system.watch(shard, terminationProbe);

            shard.tell(new HandOff('shard-1'));
            await new Promise(r => setTimeout(r, 100));

            const probeActor = system.getActor(terminationProbe.path) as TestProbe;
            const terminatedNames = probeActor.messages
                .filter(m => m instanceof Terminated)
                .map(m => m.actorRef.path.name);
            
            expect(terminatedNames).toContain('entity-1');
            expect(terminatedNames).toContain('entity-2');
            expect(terminatedNames).toContain('shard-1');
            expect(probeActor.messages.length).toBe(3);
        });
        
        test('should passivate an idle entity', async () => {
            vi.useFakeTimers();

            // Passivation timeout of 100ms
            const shard = system.actorOf(Actor.props(Shard, 'shard-1', entityProps, 0.1), 'shard-1');
            
            shard.tell(new ShardEnvelope('shard-1', 'entity-1', { type: 'increment' }));
            await vi.advanceTimersByTimeAsync(50);

            const entityRef = await system.actorSelection('akka://TestSystem/user/shard-1/entity-1');
            expect(entityRef).not.toBeNull();

            const terminationProbe = system.actorOf(Actor.props(TestProbe), 'terminationProbe');
            system.watch(entityRef!, terminationProbe);
            
            // Advance time past the passivation timeout
            await vi.advanceTimersByTimeAsync(150);

            const probeActor = system.getActor(terminationProbe.path) as TestProbe;
            expect(probeActor.messages.length).toBe(1);
            expect(probeActor.messages[0]).toBeInstanceOf(Terminated);
            expect(probeActor.messages[0].actorRef.path.name).toBe('entity-1');

            vi.useRealTimers();
        });
    });
});
