import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { ActorSystem } from './actor-system';
import { Actor } from './actor';
import type { ActorContext } from './actor-context';
import type { ActorRef } from './actor-ref';

const childPostStopMock = mock(() => {});

class ParentActor extends Actor<any> {
	public childRef: ActorRef<any> | null = null;
	public contextSnapshot: ActorContext<any> | null = null;

	receive(message: any, context: ActorContext<any>): void {
		this.contextSnapshot = context;
		if (message.action === 'spawn') {
			this.childRef = context.spawn({ type: ChildActor, props: message.childProps }, message.childName);
		} else if (message.action === 'stop' && this.childRef) {
			context.stop(this.childRef);
		} else if (message.action === 'stopNonChild' && message.ref) {
			context.stop(message.ref);
		}
	}
}

class ChildActor extends Actor<any> {
	public contextSnapshot: ActorContext<any> | null = null;
	receive(_message: any, context: ActorContext<any>): void {
		this.contextSnapshot = context;
	}
	postStop(): void {
		childPostStopMock();
	}
}

class SelfStoppingActor extends Actor<any> {
	receive(message: any, context: ActorContext<any>) {
		if (message.action === 'stop-self') {
			context.stop(context.self);
		}
	}
}

describe('ActorContext', () => {
	let system: ActorSystem;

	beforeEach(() => {
		system = ActorSystem.create('TestSystem');
		childPostStopMock.mockClear();
	});

	afterEach(async () => {
		await system.shutdown();
	});

	const getActorInstance = async <T extends Actor<any>>(ref: ActorRef<any>): Promise<T> => {
		await new Promise(resolve => setTimeout(resolve, 5));
		const cell = (system as any).actors.get(ref.path.toString());
		return cell?.instance as T;
	};

	describe('Properties', () => {
		it('should provide a correct `self` reference', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'getContext' });
			const instance = await getActorInstance<ParentActor>(parentRef);
			expect(instance.contextSnapshot).not.toBeNull();
			expect(instance.contextSnapshot?.self).toBe(parentRef);
		});

		it('should provide a correct `system` reference', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'getContext' });
			const instance = await getActorInstance<ParentActor>(parentRef);
			expect(instance.contextSnapshot).not.toBeNull();
			expect(instance.contextSnapshot?.system).toBe(system);
		});

		it('should provide a correct `parent` reference for a child actor', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'spawn', childName: 'child' });
			const parentInstance = await getActorInstance<ParentActor>(parentRef);
			const childRef = parentInstance.childRef;
			expect(childRef).not.toBeNull();

			childRef!.tell({ action: 'getContext' });
			const childInstance = await getActorInstance<ChildActor>(childRef!);
			expect(childInstance.contextSnapshot).not.toBeNull();
			expect(childInstance.contextSnapshot?.parent).toBe(parentRef);
		});

		it('should provide the user guardian as the `parent` for a top-level actor', async () => {
			const topLevelRef = system.spawn({ type: ParentActor }, 'top-level');
			topLevelRef.tell({ action: 'getContext' });
			const instance = await getActorInstance<ParentActor>(topLevelRef);
			const userGuardian = (system as any).userGuardian;

			expect(instance.contextSnapshot).not.toBeNull();
			expect(instance.contextSnapshot?.parent).toBe(userGuardian);
		});
	});

	describe('spawn()', () => {
		it('should allow an actor to spawn a child actor with a specified name', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'spawn', childName: 'child1' });
			const instance = await getActorInstance<ParentActor>(parentRef);
			const childRef = instance.childRef;

			expect(childRef).toBeDefined();
			expect(childRef?.path.name).toBe('child1');
			expect(childRef?.path.parent).toBe(parentRef.path);
			expect((system as any).actors.has(childRef!.path.toString())).toBe(true);
		});

		it('should assign a unique name if none is provided', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'spawn' });
			const instance = await getActorInstance<ParentActor>(parentRef);
			const childRef = instance.childRef;

			expect(childRef).toBeDefined();
			expect(childRef?.path.name).toMatch(/^[0-9a-f-]{36}$/);
		});

		it('should throw an error when trying to spawn a child with a duplicate name', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			const actorCell = (system as any).actors.get(parentRef.path.toString());
			actorCell.context.spawn({ type: ChildActor }, 'duplicate-name');

			expect(() => {
				actorCell.context.spawn({ type: ChildActor }, 'duplicate-name');
			}).toThrow('Actor name "duplicate-name" is already in use by a child of actor "akka://TestSystem/user/parent"');
		});
	});

	describe('stop()', () => {
		it('should allow an actor to stop one of its children', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'spawn', childName: 'child-to-stop' });
			const parentInstance = await getActorInstance<ParentActor>(parentRef);
			const childRef = parentInstance.childRef;
			expect(childRef).not.toBeNull();
			expect((system as any).actors.has(childRef!.path.toString())).toBe(true);

			parentRef.tell({ action: 'stop' });
			await new Promise(resolve => setTimeout(resolve, 5));

			expect((system as any).actors.has(childRef!.path.toString())).toBe(false);
		});

		it('should call the postStop lifecycle hook on the stopped child', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'spawn', childName: 'child-with-hook' });
			await getActorInstance<ParentActor>(parentRef);
			expect(childPostStopMock).not.toHaveBeenCalled();

			parentRef.tell({ action: 'stop' });
			await new Promise(resolve => setTimeout(resolve, 10));

			expect(childPostStopMock).toHaveBeenCalledTimes(1);
		});

		it('should not allow an actor to stop an actor that is not its child', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			const otherActorRef = system.spawn({ type: ChildActor }, 'other-actor');
			expect((system as any).actors.has(otherActorRef.path.toString())).toBe(true);

			parentRef.tell({ action: 'stopNonChild', ref: otherActorRef });
			await new Promise(resolve => setTimeout(resolve, 5));

			expect((system as any).actors.has(otherActorRef.path.toString())).toBe(true);
		});

		it('should handle stopping an already stopped child gracefully', async () => {
			const parentRef = system.spawn({ type: ParentActor }, 'parent');
			parentRef.tell({ action: 'spawn', childName: 'stoppable-child' });
			const parentInstance = await getActorInstance<ParentActor>(parentRef);
			const childRef = parentInstance.childRef;

			parentRef.tell({ action: 'stop' });
			await new Promise(resolve => setTimeout(resolve, 5));
			expect((system as any).actors.has(childRef!.path.toString())).toBe(false);

			const stopAgainFn = () => parentRef.tell({ action: 'stopNonChild', ref: childRef });
			expect(stopAgainFn).not.toThrow();
			await new Promise(resolve => setTimeout(resolve, 5));
			expect((system as any).actors.has(parentRef.path.toString())).toBe(true);
		});

		it('should not allow an actor to stop itself via context.stop(self)', async () => {
			const ref = system.spawn({ type: SelfStoppingActor }, 'self-stopper');
			ref.tell({ action: 'stop-self' });
			await new Promise(resolve => setTimeout(resolve, 5));
			expect((system as any).actors.has(ref.path.toString())).toBe(true);
		});
	});
});
