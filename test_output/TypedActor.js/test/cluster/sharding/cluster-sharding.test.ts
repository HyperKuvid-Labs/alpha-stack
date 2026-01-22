import { describe, it, expect, beforeEach, vi, afterEach } from 'bun:test';
import { ClusterSharding, ShardingProxyRef, ShardingProxy } from './cluster-sharding';
import { ActorSystem } from '../../core/actor-system';
import { Actor, ActorProps } from '../../core/actor';
import { ActorRef } from '../../core/actor-ref';
import { ActorContext } from '../../core/actor-context';
import { ShardCoordinator } from './shard-coordinator';
import { ShardRegion } from './shard-region';

vi.mock('../../core/actor-system');
vi.mock('../../core/actor-ref');
vi.mock('./shard-coordinator');

const mockTell = vi.fn();
const mockStop = vi.fn();
const mockActorOf = vi.fn();

const mockCoordinatorRef = {
	tell: mockTell,
	stop: mockStop,
	path: { toString: () => 'akka://test/system/sharding/TestEntity' },
} as unknown as ActorRef<any>;
const mockProxyRef = {
	tell: mockTell,
	stop: mockStop,
	path: { toString: () => 'akka://test/system/sharding/TestEntityProxy' },
} as unknown as ActorRef<any>;

const mockSystem = {
	actorOf: mockActorOf,
	name: 'test-system',
	log: {
		debug: vi.fn(),
		info: vi.fn(),
		warn: vi.fn(),
		error: vi.fn(),
	},
	eventStream: {
		subscribe: vi.fn(),
		unsubscribe: vi.fn(),
		publish: vi.fn(),
	},
} as unknown as ActorSystem;

const MockShardCoordinator = vi.mocked(ShardCoordinator);
MockShardCoordinator.props = vi.fn().mockReturnValue({ actorClass: ShardCoordinator, args: [] } as ActorProps<any>);

describe('ClusterSharding', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		(ClusterSharding as any).instances.clear();
	});

	describe('get', () => {
		it('should create and return a new instance for an actor system', () => {
			const sharding = ClusterSharding.get(mockSystem);
			expect(sharding).toBeInstanceOf(ClusterSharding);
		});

		it('should return the same instance for the same actor system', () => {
			const sharding1 = ClusterSharding.get(mockSystem);
			const sharding2 = ClusterSharding.get(mockSystem);
			expect(sharding1).toBe(sharding2);
		});

		it('should return different instances for different actor systems', () => {
			const mockSystem2 = { name: 'test-system-2' } as ActorSystem;
			const sharding1 = ClusterSharding.get(mockSystem);
			const sharding2 = ClusterSharding.get(mockSystem2);
			expect(sharding1).not.toBe(sharding2);
		});
	});

	describe('init', () => {
		let sharding: ClusterSharding;
		const entityProps = { actorClass: class extends Actor {}, args: [] } as ActorProps<any>;
		const extractEntityId = (message: any) => ({ entityId: message.id, message: message });
		const extractShardId = (entityId: string) => String(parseInt(entityId, 10) % 10);
		const options = {
			typeName: 'TestEntity',
			entityProps,
			extractEntityId,
			extractShardId,
		};

		beforeEach(() => {
			sharding = ClusterSharding.get(mockSystem);
			mockActorOf
				.mockImplementationOnce(() => mockCoordinatorRef)
				.mockImplementationOnce(() => mockProxyRef);
		});

		it('should initialize sharding for a new typeName and return a proxy ref', () => {
			const proxyRef = sharding.init(options);

			expect(proxyRef).toBeInstanceOf(ShardingProxyRef);
			expect(mockActorOf).toHaveBeenCalledTimes(2);

			expect(MockShardCoordinator.props).toHaveBeenCalledWith({
				typeName: 'TestEntity',
				entityProps,
				extractShardId,
				handOffStopMessage: undefined,
			});
			expect(mockActorOf).toHaveBeenCalledWith(MockShardCoordinator.props(expect.anything()), 'TestEntity');

			expect(mockActorOf).toHaveBeenCalledWith(
				expect.objectContaining({
					actorClass: ShardingProxy,
					args: expect.arrayContaining(['TestEntity', mockCoordinatorRef, extractEntityId, extractShardId]),
				}),
				'TestEntityProxy',
			);
		});

		it('should return the existing proxy ref if typeName is already initialized', () => {
			const proxyRef1 = sharding.init(options);
			const proxyRef2 = sharding.init(options);

			expect(proxyRef1).toBe(proxyRef2);
			expect(mockActorOf).toHaveBeenCalledTimes(2);
			expect(MockShardCoordinator.props).toHaveBeenCalledTimes(1);
		});

		it('should return a ShardingProxyRef that correctly forwards messages', () => {
			const proxyRef = sharding.init(options);
			const message = { id: '123', payload: 'hello' };
			proxyRef.tell(message);

			expect(mockProxyRef.tell).toHaveBeenCalledWith(message, undefined);
		});

		it('should stop the shard coordinator when the extension is stopped', async () => {
			sharding.init(options);
			await sharding.stop();
			expect(mockCoordinatorRef.stop).toHaveBeenCalled();
		});

		it('should throw an error if trying to init with a different role', () => {
			sharding.init({ ...options, role: 'role-a' });
			expect(() => sharding.init({ ...options, role: 'role-b' })).toThrow(
				"Sharding for [TestEntity] has already been started with role [role-a], but you tried to start it with role [role-b]",
			);
		});
	});
});

describe('ShardingProxy', () => {
	let proxy: ShardingProxy;
	let mockContext: ActorContext;
	const extractEntityId = vi.fn((message: any) => ({ entityId: message.id, message: message.payload }));
	const extractShardId = vi.fn((entityId: string) => String(parseInt(entityId, 10) % 2));

	beforeEach(() => {
		vi.clearAllMocks();

		mockContext = {
			self: { path: { toString: () => 'self' } } as ActorRef<any>,
			system: mockSystem,
		} as unknown as ActorContext;

		proxy = new ShardingProxy('TestEntity', mockCoordinatorRef, extractEntityId, extractShardId);
		(proxy as any).context = mockContext;
	});

	it('should extract entity and shard IDs and forward the message to the coordinator', async () => {
		const message = { id: '123', payload: 'data' };
		const innerMessage = 'data';
		extractEntityId.mockReturnValue({ entityId: '123', message: innerMessage });
		extractShardId.mockReturnValue('1');

		await proxy.receive(message);

		expect(extractEntityId).toHaveBeenCalledWith(message);
		expect(extractShardId).toHaveBeenCalledWith('123');
		expect(mockCoordinatorRef.tell).toHaveBeenCalledWith({
			type: 'ShardEnvelope',
			shardId: '1',
			entityId: '123',
			message: innerMessage,
		});
	});

	it('should log a warning and drop the message if extractEntityId returns null', async () => {
		extractEntityId.mockReturnValue(null);
		const message = { id: '456', payload: 'data' };

		await proxy.receive(message);

		expect(extractShardId).not.toHaveBeenCalled();
		expect(mockCoordinatorRef.tell).not.toHaveBeenCalled();
		expect(mockSystem.log.warn).toHaveBeenCalledWith(
			'[ShardingProxy(TestEntity)] Dropping message of type Object for entity [TestEntity] as extractEntityId returned null/undefined.',
		);
	});

	it('should log a warning and drop the message if extractEntityId returns undefined', async () => {
		extractEntityId.mockReturnValue(undefined);
		const message = { id: '789', payload: 'data' };

		await proxy.receive(message);

		expect(extractShardId).not.toHaveBeenCalled();
		expect(mockCoordinatorRef.tell).not.toHaveBeenCalled();
		expect(mockSystem.log.warn).toHaveBeenCalledWith(
			'[ShardingProxy(TestEntity)] Dropping message of type Object for entity [TestEntity] as extractEntityId returned null/undefined.',
		);
	});
});

describe('ShardingProxyRef', () => {
	it('should have a tell method that forwards to the underlying actorRef', () => {
		const underlyingRef = { tell: vi.fn(), path: { toString: () => 'path' } } as unknown as ActorRef<any>;
		const proxyRef = new ShardingProxyRef(underlyingRef);
		const message = { data: 'test' };
		const sender = { tell: vi.fn() } as unknown as ActorRef<any>;

		proxyRef.tell(message, sender);

		expect(underlyingRef.tell).toHaveBeenCalledWith(message, sender);
	});

	it('should expose the path of the underlying actorRef', () => {
		const path = { toString: () => 'akka://test/system/sharding/MyEntityProxy' };
		const underlyingRef = { tell: vi.fn(), path } as unknown as ActorRef<any>;
		const proxyRef = new ShardingProxyRef(underlyingRef);

		expect(proxyRef.path).toBe(path);
	});
});
