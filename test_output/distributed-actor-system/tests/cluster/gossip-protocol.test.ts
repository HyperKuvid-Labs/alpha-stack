import { describe, it, expect, beforeEach, afterEach, mock, spyOn } from 'bun:test';
import { GossipProtocol } from '../../src/cluster/gossip-protocol';
import { NodeManager } from '../../src/cluster/node-manager';
import { ActorSystem } from '../../src/core/actor-system';
import { Transport } from '../../src/remote/transport';
import { ActorRef, ActorAddress } from '../../src/core/actor-ref';
import type { ClusterMember } from '../../src/types/cluster.types';
import { ClusterMemberStatus } from '../../src/types/cluster.types';
import { GossipMessage } from '../../src/types/message.types';
import { Serializer } from '../../src/remote/serialization';

class MockTransport implements Transport {
  send = mock(async (_recipientAddress: ActorAddress, _payload: any, _sender?: ActorAddress, _correlationId?: string): Promise<void> => {});
  start = mock(async (): Promise<void> => {});
  stop = mock(async (): Promise<void> => {});
}

class MockNodeManager extends NodeManager {
  public localMember: ClusterMember;

  constructor(system: ActorSystem, transport: Transport, localAddress: ActorAddress) {
    super(system, transport, localAddress);
    this.localMember = {
      address: localAddress,
      status: ClusterMemberStatus.Up,
      roles: new Set(['local']),
      upNumber: 1
    };
  }
  mergeClusterState = mock((_incomingState: Map<string, ClusterMember>) => {});
}

describe('GossipProtocol', () => {
  let system: ActorSystem;
  let mockTransport: MockTransport;
  let mockNodeManager: MockNodeManager;
  let localMember: ClusterMember;
  let remoteMember1: ClusterMember;
  let remoteMember2: ClusterMember;
  let localActorAddress: ActorAddress;

  beforeEach(() => {
    mock.useFakeTimers();

    localActorAddress = ActorAddress.fromString('test-system@localhost:9001/system');
    localMember = {
      address: ActorAddress.fromString('test-system@localhost:9001'),
      status: ClusterMemberStatus.Up,
      roles: new Set(['local']),
      upNumber: 1
    };
    remoteMember1 = {
      address: ActorAddress.fromString('test-system@localhost:9002'),
      status: ClusterMemberStatus.Up,
      roles: new Set(['remote1']),
      upNumber: 1
    };
    remoteMember2 = {
      address: ActorAddress.fromString('test-system@localhost:9003'),
      status: ClusterMemberStatus.Up,
      roles: new Set(['remote2']),
      upNumber: 1
    };

    system = new ActorSystem('test-system');
    mockTransport = new MockTransport();
    mockNodeManager = new MockNodeManager(system, mockTransport, localActorAddress);
  });

  afterEach(async () => {
    await system.shutdown();
    mock.restore();
  });

  const spawnGossipActor = (gossipInterval: number = 1000): ActorRef<GossipProtocol> => {
    return system.spawn(
      new GossipProtocol(mockNodeManager, mockTransport, { gossipInterval }),
      'gossip-protocol',
    );
  };

  it('should be created successfully', () => {
    const gossipActorRef = spawnGossipActor();
    expect(gossipActorRef).toBeInstanceOf(ActorRef);
    expect(gossipActorRef.address.path).toContain('/user/gossip-protocol');
  });

  it('should start gossiping periodically after being started', () => {
    const setIntervalSpy = spyOn(global, 'setInterval');
    spawnGossipActor(1500);
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    const [handler, interval] = setIntervalSpy.mock.calls[0];
    expect(interval).toBe(1500);
  });

  it('should stop gossiping when the actor is stopped', async () => {
    const clearIntervalSpy = spyOn(global, 'clearInterval');
    const gossipActorRef = spawnGossipActor();
    await system.stop(gossipActorRef);
    expect(clearIntervalSpy).toHaveBeenCalledTimes(1);
  });

  it('should not send gossip if it is the only node in the cluster', () => {
    spyOn(mockNodeManager, 'getMembers').mockReturnValue([mockNodeManager.localMember]);
    spawnGossipActor();

    mock.tick(1000);

    expect(mockTransport.send).not.toHaveBeenCalled();
  });

  it('should send its member list to a random other node', () => {
    const allMembers = [localMember, remoteMember1, remoteMember2];
    spyOn(mockNodeManager, 'getMembers').mockReturnValue(allMembers);
    spyOn(Math, 'random').mockReturnValue(0.6);

    spawnGossipActor();
    mock.tick(1000);

    expect(mockTransport.send).toHaveBeenCalledTimes(1);

    const [targetAddress, message] = mockTransport.send.mock.calls[0];
    expect(targetAddress.toString()).toBe('test-system@localhost:9003/system/gossip');
    expect(message).toBeInstanceOf(GossipMessage);
    expect(message.members.map(m => m.address.toString())).toEqual(allMembers.map(m => m.address.toString()));

    mock.restore();
  });

  it('should correctly select the first peer when Math.random() is close to 0', () => {
    const allMembers = [localMember, remoteMember1, remoteMember2];
    spyOn(mockNodeManager, 'getMembers').mockReturnValue(allMembers);
    spyOn(Math, 'random').mockReturnValue(0.1);

    spawnGossipActor();
    mock.tick(1000);

    const [targetAddress] = mockTransport.send.mock.calls[0];
    expect(targetAddress.toString()).toBe('test-system@localhost:9002/system/gossip');
    mock.restore();
  });

  it('should correctly construct the target gossip actor address', () => {
    spyOn(mockNodeManager, 'getMembers').mockReturnValue([localMember, remoteMember1]);
    spawnGossipActor();
    mock.tick(1000);

    const [targetAddress] = mockTransport.send.mock.calls[0];
    expect(targetAddress.path.toString()).toBe('/system/gossip');
    expect(targetAddress.host).toBe('localhost');
    expect(targetAddress.port).toBe(9002);
    expect(targetAddress.system).toBe('test-system');
  });

  it('should merge incoming member lists via the NodeManager upon receiving a GossipMessage', async () => {
    const gossipActorRef = spawnGossipActor();
    const incomingMembersArray = [remoteMember1, remoteMember2];
    const incomingMembersMap = new Map(incomingMembersArray.map(m => [m.address.path, m]));
    const gossipMessage = new GossipMessage(incomingMembersArray);

    gossipActorRef.tell(gossipMessage);

    await new Promise(resolve => setImmediate(resolve));

    expect(mockNodeManager.mergeClusterState).toHaveBeenCalledTimes(1);
    expect(mockNodeManager.mergeClusterState).toHaveBeenCalledWith(incomingMembersMap);
  });

  it('should handle receiving an empty gossip message gracefully', async () => {
    const gossipActorRef = spawnGossipActor();
    const gossipMessage = new GossipMessage([]);

    gossipActorRef.tell(gossipMessage);
    await new Promise(resolve => setImmediate(resolve));

    expect(mockNodeManager.mergeClusterState).toHaveBeenCalledTimes(1);
    expect(mockNodeManager.mergeClusterState).toHaveBeenCalledWith(new Map());
  });

  it('should not throw error if transport fails to send', () => {
    spyOn(mockNodeManager, 'getMembers').mockReturnValue([localMember, remoteMember1]);
    mockTransport.send.mockImplementation(async () => {
      throw new Error('Network failure');
    });

    spawnGossipActor();

    expect(() => mock.tick(1000)).not.toThrow();
    expect(mockTransport.send).toHaveBeenCalledTimes(1);
  });
});
