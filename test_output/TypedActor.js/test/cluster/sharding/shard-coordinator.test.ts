import { describe, it, expect, beforeEach, vi } from 'bun:test';
import {
	ShardCoordinator,
	ShardCoordinatorState,
	RegisterShardRegion,
	RequestShardAllocation,
	ShardAllocated,
	ShardTerminated,
	ShardRegionRegisteredEvent,
	ShardRegionRemovedEvent,
	ShardAllocatedEvent,
	ShardTerminatedEvent,
	ShardCoordinatorEvent,
} from './shard-coordinator';
import type { ActorRef } from '../../core/actor-ref';
import type { ActorContext } from '../../core/actor-context';
import type { ActorSystem } from '../../core/actor-system';
import { Member, MemberDown, MemberUp, UnreachableMember } from '../membership/cluster-events';

const mockLogger = {
	info: vi.fn(),
	warn: vi.fn(),
	error: vi.fn(),
	debug: vi.fn(),
};

vi.mock('../../utils/logger', () => ({
	Logger: {
		getInstance: () => mockLogger,
	},
}));

class MockActorRef implements ActorRef<any> {
	public tell = vi.fn();
	constructor(public readonly path: { address: string; name: string }) {}
}

const createMockContext = (system: ActorSystem, self: ActorRef<any>): ActorContext => ({
	self,
	system,
	spawn: vi.fn(),
	stop: vi.fn(),
	watch: vi.fn(),
	unwatch: vi.fn(),
	children: new Map(),
	parent: null,
});

class TestableShardCoordinator extends ShardCoordinator {
	public state: ShardCoordinatorState;
	private eventLog: ShardCoordinatorEvent[] = [];
	public lastPersistedEvent: ShardCoordinatorEvent | null = null;

	constructor(maxShards: number, context: ActorContext) {
		super(maxShards);
		this.context = context;
		this.state = this.getInitialState();
	}

	protected persist<T extends ShardCoordinatorEvent>(event: T, handler: (event: T) => void): void {
		this.lastPersistedEvent = event;
		this.eventLog.push(event);
		handler(event);
	}

	public simulateRecovery(events: ShardCoordinatorEvent[]): void {
		this.state = this.getInitialState();
		for (const event of events) {
			this.receiveRecover(event);
		}
	}

	public getEvents(): ShardCoordinatorEvent[] {
		return this.eventLog;
	}

	public public_onMemberDown(msg: MemberDown) {
		this.onMemberDown(msg);
	}

	public public_onUnreachableMember(msg: UnreachableMember) {
		this.onUnreachableMember(msg);
	}
}

describe('ShardCoordinator', () => {
	let coordinator: TestableShardCoordinator;
	let mockSystem: ActorSystem;
	let mockContext: ActorContext;
	let mockSelfRef: MockActorRef;
	let mockRegionARef: MockActorRef;
	let mockRegionBRef: MockActorRef;

	const regionAAddress = 'akka://system@host1:2552';
	const regionBAddress = 'akka://system@host2:2552';

	beforeEach(() => {
		vi.clearAllMocks();
		mockSelfRef = new MockActorRef({ address: 'local', name: 'shardCoordinator' });
		mockRegionARef = new MockActorRef({ address: regionAAddress, name: 'shardRegion' });
		mockRegionBRef = new MockActorRef({ address: regionBAddress, name: 'shardRegion' });

		mockSystem = {
			eventStream: {
				subscribe: vi.fn(),
				unsubscribe: vi.fn(),
				publish: vi.fn(),
			},
		} as any;

		mockContext = createMockContext(mockSystem, mockSelfRef);
		coordinator = new TestableShardCoordinator(100, mockContext);
	});

	describe('Initialization and Lifecycle', () => {
		it('should start with an empty state', () => {
			expect(coordinator.state.regions).toEqual({});
			expect(coordinator.state.shards).toEqual({});
		});

		it('should subscribe to cluster events on preStart', () => {
			coordinator.preStart();
			expect(mockSystem.eventStream.subscribe).toHaveBeenCalledWith(mockSelfRef, MemberUp);
			expect(mockSystem.eventStream.subscribe).toHaveBeenCalledWith(mockSelfRef, MemberDown);
			expect(mockSystem.eventStream.subscribe).toHaveBeenCalledWith(mockSelfRef, UnreachableMember);
		});

		it('should unsubscribe from cluster events on postStop', () => {
			coordinator.postStop();
			expect(mockSystem.eventStream.unsubscribe).toHaveBeenCalledWith(mockSelfRef);
		});
	});

	describe('State Recovery', () => {
		it('should correctly recover state from a sequence of events', () => {
			const events: ShardCoordinatorEvent[] = [
				{ type: 'ShardRegionRegistered', regionRef: mockRegionARef },
				{ type: 'ShardAllocated', shardId: 'shard-1', regionRef: mockRegionARef },
				{ type: 'ShardAllocated', shardId: 'shard-2', regionRef: mockRegionARef },
				{ type: 'ShardRegionRegistered', regionRef: mockRegionBRef },
				{ type: 'ShardTerminated', shardId: 'shard-1' },
				{ type: 'ShardAllocated', shardId: 'shard-1', regionRef: mockRegionBRef },
				{ type: 'ShardRegionRemoved', regionRef: mockRegionARef },
			];

			coordinator.simulateRecovery(events);

			expect(coordinator.state.regions).toHaveProperty(mockRegionBRef.path.address);
			expect(coordinator.state.regions).not.toHaveProperty(mockRegionARef.path.address);
			expect(coordinator.state.regions[mockRegionBRef.path.address].shards).toContain('shard-1');
			expect(coordinator.state.shards['shard-1']).toBe(mockRegionBRef);
			expect(coordinator.state.shards['shard-2']).toBeUndefined();
		});
	});

	describe('Region Management', () => {
		it('should register a new shard region', () => {
			const msg = new RegisterShardRegion(mockRegionARef);
			coordinator.onRegisterShardRegion(msg);

			expect(coordinator.lastPersistedEvent).toEqual({ type: 'ShardRegionRegistered', regionRef: mockRegionARef });
			expect(coordinator.state.regions[regionAAddress]).toBeDefined();
			expect(coordinator.state.regions[regionAAddress].ref).toBe(mockRegionARef);
			expect(coordinator.state.regions[regionAAddress].shards).toEqual([]);
		});

		it('should be idempotent when registering an existing region', () => {
			const msg = new RegisterShardRegion(mockRegionARef);
			coordinator.onRegisterShardRegion(msg);
			const eventCount = coordinator.getEvents().length;

			coordinator.onRegisterShardRegion(msg);

			expect(coordinator.getEvents().length).toBe(eventCount);
			expect(Object.keys(coordinator.state.regions).length).toBe(1);
		});

		it('should remove a region and deallocate its shards on MemberDown', () => {
			coordinator.onRegisterShardRegion(new RegisterShardRegion(mockRegionARef));
			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-1', mockRegionARef));
			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-2', mockRegionARef));

			expect(coordinator.state.shards['shard-1']).toBe(mockRegionARef);
			expect(coordinator.state.shards['shard-2']).toBe(mockRegionARef);
			expect(coordinator.state.regions[regionAAddress]).toBeDefined();

			const member = new Member(regionAAddress, 'Up');
			const msg = new MemberDown(member);
			coordinator.public_onMemberDown(msg);

			expect(coordinator.lastPersistedEvent).toEqual({ type: 'ShardRegionRemoved', regionRef: mockRegionARef });
			expect(coordinator.state.regions[regionAAddress]).toBeUndefined();
			expect(coordinator.state.shards['shard-1']).toBeUndefined();
			expect(coordinator.state.shards['shard-2']).toBeUndefined();
		});

		it('should remove a region on UnreachableMember', () => {
			coordinator.onRegisterShardRegion(new RegisterShardRegion(mockRegionARef));
			const member = new Member(regionAAddress, 'Up');
			const msg = new UnreachableMember(member);
			coordinator.public_onUnreachableMember(msg);

			expect(coordinator.lastPersistedEvent).toEqual({ type: 'ShardRegionRemoved', regionRef: mockRegionARef });
			expect(coordinator.state.regions[regionAAddress]).toBeUndefined();
		});

		it('should not remove a region if member address does not match', () => {
			coordinator.onRegisterShardRegion(new RegisterShardRegion(mockRegionARef));

			const member = new Member('akka://system@some-other-host:2552', 'Up');
			const msg = new MemberDown(member);
			coordinator.public_onMemberDown(msg);

			expect(coordinator.lastPersistedEvent).toBeNull();
			expect(coordinator.state.regions[regionAAddress]).toBeDefined();
		});
	});

	describe('Shard Allocation and Termination', () => {
		beforeEach(() => {
			coordinator.onRegisterShardRegion(new RegisterShardRegion(mockRegionARef));
			coordinator.onRegisterShardRegion(new RegisterShardRegion(mockRegionBRef));
		});

		it('should allocate a new shard to the least busy region', () => {
			const requestMsg = new RequestShardAllocation('shard-1', mockRegionARef);
			coordinator.onRequestShardAllocation(requestMsg);

			expect(coordinator.lastPersistedEvent).toEqual({ type: 'ShardAllocated', shardId: 'shard-1', regionRef: mockRegionARef });
			expect(mockRegionARef.tell).toHaveBeenCalledWith(new ShardAllocated('shard-1'));
			expect(coordinator.state.shards['shard-1']).toBe(mockRegionARef);
			expect(coordinator.state.regions[regionAAddress].shards).toContain('shard-1');
		});

		it('should balance shard allocation across regions', () => {
			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-1', mockRegionARef));
			expect(coordinator.state.shards['shard-1']).toBe(mockRegionARef);
			expect(mockRegionARef.tell).toHaveBeenCalledWith(new ShardAllocated('shard-1'));

			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-2', mockRegionBRef));
			expect(coordinator.state.shards['shard-2']).toBe(mockRegionBRef);
			expect(mockRegionBRef.tell).toHaveBeenCalledWith(new ShardAllocated('shard-2'));

			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-3', mockRegionARef));
			expect(coordinator.state.shards['shard-3']).toBe(mockRegionARef);
			expect(mockRegionARef.tell).toHaveBeenCalledWith(new ShardAllocated('shard-3'));
		});

		it('should return the existing allocation if a shard is already allocated', () => {
			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-1', mockRegionARef));
			const eventCount = coordinator.getEvents().length;

			const secondRequestMsg = new RequestShardAllocation('shard-1', mockRegionBRef);
			coordinator.onRequestShardAllocation(secondRequestMsg);

			expect(coordinator.getEvents().length).toBe(eventCount);

			expect(mockRegionBRef.tell).toHaveBeenCalledWith(new ShardAllocated('shard-1', mockRegionARef));
		});

		it('should deallocate a shard on ShardTerminated message', () => {
			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-1', mockRegionARef));
			expect(coordinator.state.shards['shard-1']).toBe(mockRegionARef);

			const terminateMsg = new ShardTerminated('shard-1');
			coordinator.onShardTerminated(terminateMsg);

			expect(coordinator.lastPersistedEvent).toEqual({ type: 'ShardTerminated', shardId: 'shard-1' });
			expect(coordinator.state.shards['shard-1']).toBeUndefined();
			expect(coordinator.state.regions[regionAAddress].shards).not.toContain('shard-1');
		});

		it('should reallocate a terminated shard upon a new request', () => {
			coordinator.onRequestShardAllocation(new RequestShardAllocation('shard-1', mockRegionARef));
			coordinator.onShardTerminated(new ShardTerminated('shard-1'));

			const requestMsg = new RequestShardAllocation('shard-1', mockRegionBRef);
			coordinator.onRequestShardAllocation(requestMsg);

			expect(coordinator.lastPersistedEvent).toEqual({ type: 'ShardAllocated', shardId: 'shard-1', regionRef: mockRegionBRef });
			expect(mockRegionBRef.tell).toHaveBeenCalledWith(new ShardAllocated('shard-1'));
			expect(coordinator.state.shards['shard-1']).toBe(mockRegionBRef);
		});

		it('should not allocate a shard if no regions are registered', () => {
			const newCoordinator = new TestableShardCoordinator(100, mockContext);
			const requestMsg = new RequestShardAllocation('shard-1', new MockActorRef({ address: 'none', name: 'test' }));

			newCoordinator.onRequestShardAllocation(requestMsg);

			expect(newCoordinator.getEvents().length).toBe(0);
			expect(mockLogger.warn).toHaveBeenCalledWith(expect.stringContaining('No shard regions registered'));
		});
	});
});
