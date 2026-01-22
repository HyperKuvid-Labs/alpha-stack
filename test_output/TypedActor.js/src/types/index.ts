// Core Actor System Types
export { Actor } from '../core/actor';
export { ActorContext } from '../core/actor-context';
export { ActorRef } from '../core/actor-ref';
export { ActorSystem } from '../core/actor-system';

// Cluster Types
export { MemberDown, MemberUp, UnreachableMember } from '../cluster/membership/cluster-events';
export { MembershipProvider } from '../cluster/membership/membership-provider';
export { Serializer } from '../cluster/remote/serialization';
export { ClusterSharding } from '../cluster/sharding/cluster-sharding';

// Decorators
export { handle } from '../decorators/handle-message';

// Message Types
export { Failure, PoisonPill } from './messages';

// Persistence Types
export { JournalPlugin } from '../persistence/journal/journal-plugin';
export { PersistentActor } from '../persistence/persistent-actor';

// Supervision Types
export { SupervisionStrategy, Supervisor } from '../supervision/strategy';

// Utility Types
export { Logger } from '../utils/logger';

// Fundamental Type Definitions
import { Actor } from '../core/actor';
export type ActorProps<TMessage = any> = () => Actor<TMessage>;
