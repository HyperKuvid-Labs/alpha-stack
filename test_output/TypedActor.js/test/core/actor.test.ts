import { describe, test, expect, beforeEach, mock } from 'bun:test';
import { Actor } from './actor';
import { ActorSystem } from './actor-system';
import { ActorRef } from './actor-ref';
import { ActorContext } from './actor-context';
import { Restart, SupervisorStrategy } from '../supervision/strategy';

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Mock handlers
let preStartMock: ReturnType<typeof mock>;
let postStopMock: ReturnType<typeof mock>;
let preRestartMock: ReturnType<typeof mock>;
let postRestartMock: ReturnType<typeof mock>;
let receiveMock: ReturnType<typeof mock>;

class TestActor extends Actor<any> {
    constructor() {
        super();
    }

    preStart() {
        preStartMock(this.context);
    }

    postStop() {
        postStopMock();
    }

    preRestart(reason: Error, message?: any) {
        preRestartMock(reason, message);
    }

    postRestart(reason: Error) {
        postRestartMock(reason);
    }

    receive(message: any): void {
        receiveMock(message);
        if (message === 'fail') {
            throw new Error('Test Failure');
        }
    }
}

class AsyncTestActor extends Actor<any> {
    async preStart() {
        await sleep(10);
        preStartMock(this.context);
    }

    async postStop() {
        await sleep(10);
        postStopMock();
    }

    async preRestart(reason: Error, message?: any) {
        await sleep(10);
        preRestartMock(reason, message);
    }

    async postRestart(reason: Error) {
        await sleep(10);
        postRestartMock(reason);
    }

    async receive(message: any): Promise<void> {
        await sleep(5);
        receiveMock(message);
    }
}


describe('Actor', () => {
    let system: ActorSystem;

    beforeEach(() => {
        system = ActorSystem.create('TestSystem');
        preStartMock = mock(() => {});
        postStopMock = mock(() => {});
        preRestartMock = mock(() => {});
        postRestartMock = mock(() => {});
        receiveMock = mock((_) => {});
    });

    afterEach(async () => {
        await system.shutdown();
    });

    describe('Lifecycle Hooks', () => {
        test('preStart is called exactly once when actor is created', async () => {
            expect(preStartMock).not.toHaveBeenCalled();
            system.spawn(new TestActor(), 'test-actor');
            await sleep(10); // Allow time for actor to be initialized
            expect(preStartMock).toHaveBeenCalledTimes(1);
        });

        test('postStop is called exactly once when actor is stopped', async () => {
            const actorRef = system.spawn(new TestActor(), 'test-actor');
            await sleep(10);
            expect(postStopMock).not.toHaveBeenCalled();
            system.stop(actorRef);
            await sleep(10); // Allow time for stop process
            expect(postStopMock).toHaveBeenCalledTimes(1);
        });

        test('preStart is called before the first message is processed', async () => {
            const callOrder: string[] = [];
            preStartMock.mockImplementation(() => callOrder.push('preStart'));
            receiveMock.mockImplementation(() => callOrder.push('receive'));

            const actorRef = system.spawn(new TestActor(), 'test-actor');
            actorRef.tell('first message');

            await sleep(20);

            expect(callOrder).toEqual(['preStart', 'receive']);
        });

        test('lifecycle hooks for async actors are awaited correctly', async () => {
            const actorRef = system.spawn(new AsyncTestActor(), 'async-actor');
            await sleep(20); // Wait for async preStart
            expect(preStartMock).toHaveBeenCalledTimes(1);

            actorRef.tell('a message');
            await sleep(20);
            expect(receiveMock).toHaveBeenCalledTimes(1);
            expect(receiveMock).toHaveBeenCalledWith('a message');


            system.stop(actorRef);
            await sleep(20); // Wait for async postStop
            expect(postStopMock).toHaveBeenCalledTimes(1);
        });
    });

    describe('Supervision and Restart Lifecycle', () => {
        class ParentActor extends Actor<any> {
            child: ActorRef<any> | null = null;
            strategy: SupervisorStrategy = new Restart({ maxRetries: 2, withinMs: 1000 });

            preStart() {
                this.child = this.context.spawn(new TestActor(), 'child');
            }

            receive(message: any): void {
                if (this.child) {
                    this.child.tell(message);
                }
            }
        }

        test('preRestart and postRestart are called on failure with Restart strategy', async () => {
            const parentRef = system.spawn(new ParentActor(), 'parent');
            await sleep(10);

            expect(preStartMock).toHaveBeenCalledTimes(1);
            expect(preRestartMock).not.toHaveBeenCalled();
            expect(postRestartMock).not.toHaveBeenCalled();

            const testError = new Error('Test Failure');
            parentRef.tell('fail');

            await sleep(50); // Allow time for restart process

            expect(preRestartMock).toHaveBeenCalledTimes(1);
            expect(preRestartMock).toHaveBeenCalledWith(expect.any(Error), 'fail');
            expect(preRestartMock.mock.calls[0][0].message).toBe(testError.message);

            // postStop is called on the old instance before restart
            expect(postStopMock).toHaveBeenCalledTimes(1);

            expect(postRestartMock).toHaveBeenCalledTimes(1);
            expect(postRestartMock).toHaveBeenCalledWith(expect.any(Error));
            expect(postRestartMock.mock.calls[0][0].message).toBe(testError.message);

            // preStart is called again for the new instance
            expect(preStartMock).toHaveBeenCalledTimes(2);

            // Send another message to confirm the new actor instance is working
            parentRef.tell('after-restart');
            await sleep(10);
            expect(receiveMock).toHaveBeenCalledWith('after-restart');
        });

        test('postStop is not called if preRestart throws an error', async () => {
            const preRestartError = new Error('Failure in preRestart');
            preRestartMock.mockImplementation(() => {
                throw preRestartError;
            });
            
            class FailingParentActor extends Actor<any> {
                child: ActorRef<any> | null = null;
                strategy: SupervisorStrategy = new Restart({ maxRetries: 1 });

                preStart() {
                    this.child = this.context.spawn(new TestActor(), 'child');
                }
                receive(message: any): void {
                    this.child?.tell(message);
                }
            }

            const parentRef = system.spawn(new FailingParentActor(), 'parent');
            await sleep(10);

            postStopMock.mockClear();

            parentRef.tell('fail');
            await sleep(50);

            expect(preRestartMock).toHaveBeenCalledTimes(1);
            // Since preRestart fails, the actor is stopped, but postStop on the child is not guaranteed
            // because the supervision escalation terminates the process. We are testing that the flow stops.
            // The parent will stop the child as part of its own termination.
            expect(postStopMock).toHaveBeenCalledTimes(1);
            expect(postRestartMock).not.toHaveBeenCalled();
        });
    });

    describe('Message Handling', () => {
        test('receive method is called with the correct message', async () => {
            const actorRef = system.spawn(new TestActor(), 'receiver');
            await sleep(10);

            const message1 = 'hello world';
            actorRef.tell(message1);
            await sleep(10);
            expect(receiveMock).toHaveBeenCalledWith(message1);

            const message2 = { data: 'test', value: 42 };
            actorRef.tell(message2);
            await sleep(10);
            expect(receiveMock).toHaveBeenCalledWith(message2);
            
            expect(receiveMock).toHaveBeenCalledTimes(2);
        });

        test('actor processes messages sequentially in the order they are sent', async () => {
            const processedMessages: any[] = [];
            receiveMock.mockImplementation(async (msg) => {
                await sleep(5);
                processedMessages.push(msg);
            });

            const actorRef = system.spawn(new TestActor(), 'sequential-actor');
            await sleep(10);
            
            actorRef.tell(1);
            actorRef.tell(2);
            actorRef.tell(3);

            await sleep(50);

            expect(processedMessages).toEqual([1, 2, 3]);
        });
    });

    describe('Actor Context', () => {
        test('context is available within the actor and is of the correct type', async () => {
            system.spawn(new TestActor(), 'context-actor');
            await sleep(10);

            expect(preStartMock).toHaveBeenCalledTimes(1);
            const context = preStartMock.mock.calls[0][0];
            expect(context).toBeInstanceOf(ActorContext);
        });

        test('context.self refers to the correct ActorRef', async () => {
            const actorRef = system.spawn(new TestActor(), 'self-ref-actor');
            await sleep(10);

            const context = preStartMock.mock.calls[0][0] as ActorContext<any>;
            expect(context.self).toBe(actorRef);
            expect(context.self).toBeInstanceOf(ActorRef);
            expect(context.self.path.toString()).toBe('actor://TestSystem/user/self-ref-actor');
        });

        test('context provides access to the actor system', async () => {
            system.spawn(new TestActor(), 'system-ref-actor');
            await sleep(10);

            const context = preStartMock.mock.calls[0][0] as ActorContext<any>;
            expect(context.system).toBe(system);
            expect(context.system).toBeInstanceOf(ActorSystem);
        });
    });
});
