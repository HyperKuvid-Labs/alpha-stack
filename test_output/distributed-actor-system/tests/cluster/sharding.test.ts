import { describe, it, expect, beforeEach, vi, mock } from 'bun:test';
import {
    ClusterSharding,
    ShardRouter,
    ShardRegionActor,
    EntityEnvelope,
    InternalShardedActorRef,
} from '../../src/cluster/sharding';
import { ActorSystem } from '../../src/core/actor-system';
import { Actor } from '../../src/core/actor';
import { Receive } from '../../src/core/decorators';
import { ActorContext, ActorProps } from '../../src/types/actor.types';
import { ActorRef, Address, Nobody } from '../../src/core/actor-ref';
import { NodeManager } from '../../src/cluster/node-manager';
import type { ClusterMember, ShardingOptions } from '../../src/types/cluster.types';
import { Transport } from '../../src/remote/transport';
import { Message } from '../../src/types/message.types';

class TestActor extends Actor<any> {
    @Receive(String)
    handleString(msg: string) {
        if (this.context.sender && this.context.sender !== Nobody) {
            this.context.sender.tell(`ack:${msg}`);
        }
    }

    @Receive(Object)
    handleObject(msg: { command: string }) {
        if (msg.command === 'get-self') {
            this.context.sender?.tell(this.context.self);
        }
    }
}

const mockMembers: ClusterMember[] = [
    { id: 'node-1', address: 'system@localhost:8001', roles: new Set(['worker']), status: 'up' },
    { id: 'node-2', address: 'system@localhost:8002', roles: new Set(['worker']), status: 'up' },
    { id: 'node-3', address: 'system@localhost:8003', roles: new Set(['worker']), status: 'up' },
];

describe('ShardRouter', () => {
    const numberOfShards = 100;
    let mockNodeManager: NodeManager;
    let mockActorAddress: Address;

    beforeEach(() => {
        mockNodeManager = {
            getMembers: () => mockMembers,
            getLocalMember: () => mockMembers[0],
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager;

        mockActorAddress = Address.fromString('system@localhost:8001/system');
    });

    it('should consistently map an entityId to the same shardId', () => {
        const router1 = new ShardRouter(numberOfShards, mockNodeManager, mockActorAddress);
        const router2 = new ShardRouter(numberOfShards, mockNodeManager, mockActorAddress);

        const entityId = 'customer-123';
        const shardId1 = router1.getShardId(entityId);
        const shardId2 = router2.getShardId(entityId);

        expect(shardId1).toBe(shardId2);
        expect(shardId1).toBeGreaterThanOrEqual(0);
        expect(shardId1).toBeLessThan(numberOfShards);
    });

    it('should map a shardId to a member', () => {
        const router = new ShardRouter(numberOfShards, mockNodeManager, mockActorAddress);
        const shardId = 42;
        const member = router.getMemberForShard(shardId);
        expect(member).toBe(mockMembers[shardId % mockMembers.length]);
    });

    it('should map an entityId directly to a member', () => {
        const router = new ShardRouter(numberOfShards, mockNodeManager, mockActorAddress);
        const entityId = 'product-abc';
        const shardId = router.getShardId(entityId);
        const expectedMember = router.getMemberForShard(shardId);
        const member = router.getMemberForEntity(entityId);

        expect(member).toBe(expectedMember);
    });

    it('should return undefined if no members are available', () => {
        const emptyNodeManager = {
            getMembers: () => [],
            getLocalMember: () => undefined,
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager;
        const router = new ShardRouter(numberOfShards, emptyNodeManager, mockActorAddress);
        const shardId = 42;
        expect(router.getMemberForShard(shardId)).toBeUndefined();
    });

    it('should rebalance shards when members change', () => {
        const nodeManager1 = {
            getMembers: () => mockMembers,
            getLocalMember: () => mockMembers[0],
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager;
        const router1 = new ShardRouter(numberOfShards, nodeManager1, mockActorAddress);
        const entityId = 'order-xyz';
        const member1 = router1.getMemberForEntity(entityId);

        const newMembers = [...mockMembers, { id: 'node-4', address: 'system@localhost:8004', roles: new Set(), status: 'up' }];
        const nodeManager2 = {
            getMembers: () => newMembers,
            getLocalMember: () => mockMembers[0],
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager;
        const router2 = new ShardRouter(numberOfShards, nodeManager2, mockActorAddress);
        const member2 = router2.getMemberForEntity(entityId);

        const removedMembers = [mockMembers[0], mockMembers[2]];
        const nodeManager3 = {
            getMembers: () => removedMembers,
            getLocalMember: () => mockMembers[0],
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager;
        const router3 = new ShardRouter(numberOfShards, nodeManager3, mockActorAddress);
        const member3 = router3.getMemberForEntity(entityId);

        expect(member1).toBeDefined();
        expect(mockMembers).toContain(member1);

        expect(member2).toBeDefined();
        expect(newMembers).toContain(member2);

        expect(member3).toBeDefined();
        expect(removedMembers).toContain(member3);
    });
});

describe('ShardRegionActor', () => {
    let system: ActorSystem;

    beforeEach(async () => {
        system = await ActorSystem.create('test-system');
    });

    it('should create a child entity actor on first message and forward it', async () => {
        const probe = await system.actorOf(TestActor, 'probe');
        const regionProps: ActorProps<ShardRegionActor> = {
            entityProps: {
                Cls: TestActor,
                name: 'test-entity',
            },
        };
        const region = await system.actorOf(ShardRegionActor, 'test-region', regionProps);

        const entityId = 'entity-1';
        const message = 'hello';
        const envelope: EntityEnvelope = { entityId, message };

        region.tell(envelope, probe);

        const response = await probe.ask('get-state', 100);
        expect(response).toBe('ack:hello');

        const children = await region.ask({ command: 'get-children' });
        expect(children).toBeInstanceOf(Map);
        expect((children as Map<string, any>).size).toBe(1);
        expect((children as Map<string, any>).has(entityId)).toBe(true);
    });

    it('should forward subsequent messages to the existing child actor', async () => {
        const probe = await system.actorOf(TestActor, 'probe');
        const regionProps: ActorProps<ShardRegionActor> = {
            entityProps: {
                Cls: TestActor,
                name: 'test-entity',
            },
        };
        const region = await system.actorOf(ShardRegionActor, 'test-region', regionProps);

        const entityId = 'entity-1';

        region.tell({ entityId, message: 'msg1' }, probe);
        await probe.ask('get-state', 100);

        region.tell({ entityId, message: 'msg2' }, probe);
        const response2 = await probe.ask('get-state', 100);

        expect(response2).toBe('ack:msg2');

        const children = await region.ask({ command: 'get-children' });
        expect((children as Map<string, any>).size).toBe(1);
    });
});

describe('InternalShardedActorRef', () => {
    it('should route messages correctly to the remote shard region', () => {
        const mockSystem = {
            transport: {
                send: vi.fn(),
            },
        } as unknown as ActorSystem;

        const mockSharding = {
            getRouterFor: vi.fn(),
            system: mockSystem,
        } as unknown as ClusterSharding;

        const mockNodeManager = {
            getMembers: () => mockMembers,
            getLocalMember: () => mockMembers[0],
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager;
        const mockActorAddress = Address.fromString('system@localhost:8001/system');


        const router = new ShardRouter(10, mockNodeManager, mockActorAddress);
        vi.spyOn(mockSharding, 'getRouterFor').mockReturnValue(router);

        const typeName = 'MyActor';
        const entityId = 'my-entity-1';
        const ref = new InternalShardedActorRef(mockSharding, typeName, entityId);

        const message = { data: 'test' };
        ref.tell(message);

        const member = router.getMemberForEntity(entityId);
        const expectedRegionAddress = Address.fromString(`${member.address}/system/sharding/${typeName}`);
        const expectedEnvelope: EntityEnvelope = { entityId, message };

        expect(mockSharding.getRouterFor).toHaveBeenCalledWith(typeName);
        expect(mockSystem.transport.send).toHaveBeenCalledWith(
            expect.objectContaining({
                recipient: expectedRegionAddress,
                payload: expectedEnvelope,
            }),
        );
    });
});

describe('ClusterSharding', () => {
    let system: ActorSystem;
    let sharding: ClusterSharding;

    beforeEach(async () => {
        system = await ActorSystem.create('test-cluster-system', {
            nodeId: 'node-1',
            hostname: 'localhost',
            port: 8001,
        });

        // Mock NodeManager and Transport
        system.registerExtension('nodeManager', {
            getMembers: () => mockMembers,
            getLocalMember: () => mockMembers[0],
            on: vi.fn(),
            mergeClusterState: vi.fn(),
            init: vi.fn(),
            shutdown: vi.fn(),
        } as unknown as NodeManager);

        system.registerExtension('transport', {
            send: vi.fn((msg: Message) => {
                // loopback for local messages
                system.dispatch(msg);
            }),
        } as unknown as Transport);

        sharding = new ClusterSharding(system);
        sharding.start();
    });

    it('should initialize a sharded entity and start local shard regions', async () => {
        const options: ShardingOptions = {
            typeName: 'TestEntity',
            entityProps: { Cls: TestActor, name: 'test-entity-actor' },
            numberOfShards: 10,
        };

        await sharding.init(options);

        const router = sharding.getRouterFor('TestEntity');
        expect(router).toBeInstanceOf(ShardRouter);

        let localRegions = 0;
        for (let i = 0; i < options.numberOfShards; i++) {
            if (router.getMemberForShard(i) === mockMembers[0]) {
                localRegions++;
                const regionRef = await system.findActor(`system/sharding/TestEntity/${i}`);
                expect(regionRef).not.toBe(Nobody);
            }
        }
        expect(localRegions).toBeGreaterThan(0);
    });

    it('should throw if initializing the same typeName twice', async () => {
        const options: ShardingOptions = {
            typeName: 'DuplicateEntity',
            entityProps: { Cls: TestActor, name: 'de' },
        };
        await sharding.init(options);
        await expect(sharding.init(options)).rejects.toThrow('Sharding for typeName DuplicateEntity already initialized.');
    });

    it('should provide an entity ref that can be used to send messages', async () => {
        const typeName = 'MyTestActor';
        await sharding.init({
            typeName,
            entityProps: { Cls: TestActor, name: 'mta' },
            numberOfShards: 1, // Force all shards to be local for this test
        });
        
        const localMemberOnlyManager = {
             getMembers: () => [mockMembers[0]],
             getLocalMember: () => mockMembers[0],
             on: vi.fn(),
             mergeClusterState: vi.fn(),
             init: vi.fn(),
             shutdown: vi.fn(),
        } as unknown as NodeManager
        system.registerExtension('nodeManager', localMemberOnlyManager);
        sharding.updateRouter(typeName);


        const entityId = 'user-42';
        const entityRef = sharding.entityRefFor(typeName, entityId);
        expect(entityRef).toBeInstanceOf(InternalShardedActorRef);

        const probe = await system.actorOf(TestActor, 'probe-2');

        entityRef.tell('ping', probe);
        const response = await probe.ask('get-state', 200);

        expect(response).toBe('ack:ping');

        // Check that the underlying actor was created
        const regionRef = await system.findActor(`system/sharding/${typeName}/0`);
        const children = await regionRef.ask({command: 'get-children'});
        expect((children as Map<string, ActorRef>).has(entityId)).toBe(true);
    });

    it('should throw when getting a ref for an uninitialized type', () => {
        expect(() => sharding.entityRefFor('NonExistentType', 'id-1')).toThrow(
            'Sharding for typeName NonExistentType has not been initialized. Call ClusterSharding.init() first.',
        );
    });
});
