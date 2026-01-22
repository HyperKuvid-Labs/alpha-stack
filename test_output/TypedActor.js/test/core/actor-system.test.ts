import { expect, test, describe, beforeEach, afterEach, spyOn } from 'bun:test';
import { ActorSystem } from './actor-system';
import { Actor, ActorProps, ActorConstructor } from './actor';
import { ActorRef } from './actor-ref';
import { handle } from '../decorators/handle-message';
import { SupervisionStrategy, Supervisor } from '../supervision/strategy';
import { PoisonPill } from '../types/messages';
import { ActorContext } from './actor-context';

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

class TestProbe {
    public ref: ActorRef<string>;
    private messages: string[] = [];
    private resolvers: Map<string, Array<{ resolve: () => void; reject: (reason?: any) => void; timer: Timer }>> = new Map();

    constructor(system: ActorSystem, name: string = 'test-probe') {
        class ProbeActor extends Actor<string> {
            constructor(private probe: TestProbe) {
                super({});
            }
            @handle(String)
            onMessage(message: string) {
                this.probe.addMessage(message);
            }
        }
        this.ref = system.spawn(name, ProbeActor, this);
    }

    private addMessage(message: string) {
        this.messages.push(message);
        const waiting = this.resolvers.get(message);
        if (waiting) {
            const resolver = waiting.shift();
            if (resolver) {
                clearTimeout(resolver.timer);
                resolver.resolve();
            }
            if (waiting.length === 0) {
                this.resolvers.delete(message);
            }
        }
    }

    expectMessage(message: string, timeout = 1000): Promise<void> {
        const existingIndex = this.messages.indexOf(message);
        if (existingIndex > -1) {
            this.messages.splice(existingIndex, 1);
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                const waiting = this.resolvers.get(message);
                if (waiting) {
                    const selfIndex = waiting.findIndex(w => w.timer === timer);
                    if (selfIndex > -1) {
                        waiting.splice(selfIndex, 1);
                    }
                }
                reject(new Error(`Timeout waiting for message: "${message}". Received so far: [${this.messages.join(', ')}]`));
            }, timeout);

            if (!this.resolvers.has(message)) {
                this.resolvers.set(message, []);
            }
            this.resolvers.get(message)!.push({ resolve, reject, timer });
        });
    }

    expectNoMessage(timeout = 200): Promise<void> {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                if (this.messages.length === 0) {
                    resolve();
                } else {
                    reject(new Error(`Expected no messages, but received: [${this.messages.join(', ')}]`));
                }
            }, timeout);
        });
    }
}

class EchoActor extends Actor<any> {
    @handle(Object)
    onMessage(message: any, sender: ActorRef<any>) {
        sender.tell(message);
    }
}

class LifecycleActor extends Actor<any> {
    constructor(private props: { probe: ActorRef<string> }) {
        super(props);
    }

    preStart() {
        this.props.probe.tell('preStart');
    }

    postStop() {
        this.props.probe.tell('postStop');
    }

    preRestart(reason: Error, message?: any) {
        this.props.probe.tell('preRestart');
    }

    postRestart(reason: Error) {
        this.props.probe.tell('postRestart');
    }

    @handle('error')
    onError() {
        throw new Error('test-failure');
    }
}

class ChildActor extends Actor<any> {
    constructor(private props: { probe: ActorRef<string> }) {
        super(props);
    }

    preStart() { this.props.probe.tell('child:preStart'); }
    postStop() { this.props.probe.tell('child:postStop'); }
    preRestart(reason: Error, message?: any) { this.props.probe.tell('child:preRestart'); }
    postRestart(reason: Error) { this.props.probe.tell('child:postRestart'); }

    @handle('error')
    onError() { throw new Error('child-failure'); }

    @handle('ping')
    onPing(_: 'ping', sender: ActorRef<string>) { sender.tell('pong'); }
}


class ParentActor extends Actor<any> implements Supervisor {
    child: ActorRef<any> | null = null;
    constructor(private props: { strategy: SupervisionStrategy; probe: ActorRef<string>; childConstructor: ActorConstructor<any> }) {
        super(props);
    }

    strategy = this.props.strategy;

    preStart() {
        this.props.probe.tell('parent:preStart');
        this.child = this.context.spawn('child', this.props.childConstructor, { probe: this.props.probe });
    }
    postStop() { this.props.probe.tell('parent:postStop'); }
    preRestart(reason: Error, message?: any) { this.props.probe.tell('parent:preRestart'); }
    postRestart(reason: Error) { this.props.probe.tell('parent:postRestart'); }

    @handle('tell-child')
    onTellChild(message: any) {
        if (this.child) {
            this.child.tell(message);
        }
    }
    @handle('error')
    onError() { throw new Error('parent-failure'); }
}


describe('ActorSystem', () => {
    let system: ActorSystem;
    const systemName = 'test-system';

    beforeEach(() => {
        ActorSystem.systems.delete(systemName);
        system = ActorSystem.create(systemName);
    });

    afterEach(async () => {
        if (ActorSystem.systems.has(systemName)) {
            await system.terminate();
        }
    });

    describe('create', () => {
        test('should create a new ActorSystem instance', () => {
            expect(system).toBeInstanceOf(ActorSystem);
            expect(system.name).toBe(systemName);
        });

        test('should return the same instance when called with the same name', () => {
            const system2 = ActorSystem.create(systemName);
            expect(system).toBe(system2);
        });

        test('should create different instances for different names', () => {
            const system2 = ActorSystem.create('another-system');
            expect(system).not.toBe(system2);
            system2.terminate();
        });
    });

    describe('spawn', () => {
        test('should spawn a new top-level actor', async () => {
            const probe = new TestProbe(system);
            const echo = system.spawn('echo-1', EchoActor);
            echo.tell('hello', probe.ref);
            await probe.expectMessage('hello');
        });

        test('should throw an error when spawning an actor with a duplicate name', () => {
            system.spawn('duplicate-actor', EchoActor);
            expect(() => {
                system.spawn('duplicate-actor', EchoActor);
            }).toThrow('Actor with name duplicate-actor already exists');
        });

        test('should pass props to the actor constructor', async () => {
            class PropsActor extends Actor<any> {
                constructor(private props: { value: number }) {
                    super(props);
                }
                @handle('get_value')
                onGetValue(_: any, sender: ActorRef<number>) {
                    sender.tell(this.props.value);
                }
            }
            const probe = new TestProbe(system);
            const propsActor = system.spawn('props-actor', PropsActor, { value: 42 });
            propsActor.tell('get_value', probe.ref);
            await probe.expectMessage(42 as any);
        });
    });

    describe('stop', () => {
        test('should stop an actor and invoke its postStop hook', async () => {
            const probe = new TestProbe(system);
            const actor = system.spawn('lifecycle-actor', LifecycleActor, { probe: probe.ref });
            await probe.expectMessage('preStart');
            system.stop(actor);
            await probe.expectMessage('postStop');
        });

        test('should stop child actors when a parent is stopped', async () => {
            const probe = new TestProbe(system);
            const parent = system.spawn('parent-to-stop', ParentActor, { strategy: SupervisionStrategy.Stop, probe: probe.ref, childConstructor: ChildActor });
            await probe.expectMessage('parent:preStart');
            await probe.expectMessage('child:preStart');

            system.stop(parent);

            await probe.expectMessage('child:postStop');
            await probe.expectMessage('parent:postStop');
        });

        test('should allow resusing an actor name after it has been stopped', async () => {
            const probe = new TestProbe(system);
            const actor = system.spawn('reusable-name', EchoActor);
            system.stop(actor);

            await sleep(50); // allow for stop to process

            const newActor = system.spawn('reusable-name', EchoActor);
            expect(newActor).toBeDefined();
            newActor.tell('ping', probe.ref);
            await probe.expectMessage('ping');
        });
    });

    describe('terminate', () => {
        test('should stop all actors and shutdown the system', async () => {
            const probe = new TestProbe(system, 'probe');
            system.spawn('actor-1', LifecycleActor, { probe: probe.ref });
            system.spawn('actor-2', LifecycleActor, { probe: probe.ref });

            await probe.expectMessage('preStart');
            await probe.expectMessage('preStart');

            await system.terminate();
            await probe.expectMessage('postStop');
            await probe.expectMessage('postStop');

            expect(ActorSystem.systems.has(systemName)).toBe(false);
        });

        test('should allow creating a new system with the same name after termination', async () => {
            await system.terminate();
            const newSystem = ActorSystem.create(systemName);
            expect(newSystem).toBeInstanceOf(ActorSystem);
            expect(newSystem).not.toBe(system);
        });
    });

    describe('Supervision', () => {
        let errorSpy: any;

        beforeEach(() => {
            errorSpy = spyOn(console, 'error').mockImplementation(() => {});
        });

        afterEach(() => {
            errorSpy.mockRestore();
        });

        test('Restart strategy should restart a failed child', async () => {
            const probe = new TestProbe(system);
            const parent = system.spawn('parent', ParentActor, { strategy: SupervisionStrategy.Restart, probe: probe.ref, childConstructor: ChildActor });

            await probe.expectMessage('parent:preStart');
            await probe.expectMessage('child:preStart');

            parent.tell('tell-child', 'error');

            await probe.expectMessage('child:preRestart');
            await probe.expectMessage('child:postRestart');
            await probe.expectMessage('child:preStart');

            parent.tell('tell-child', 'ping', probe.ref);
            await probe.expectMessage('pong');
        });

        test('Stop strategy should stop a failed child', async () => {
            const probe = new TestProbe(system);
            const parent = system.spawn('parent', ParentActor, { strategy: SupervisionStrategy.Stop, probe: probe.ref, childConstructor: ChildActor });

            await probe.expectMessage('parent:preStart');
            await probe.expectMessage('child:preStart');

            parent.tell('tell-child', 'error');

            await probe.expectMessage('child:postStop');

            parent.tell('tell-child', 'ping', probe.ref);
            await probe.expectNoMessage(200);
        });

        test('Resume strategy should ignore the fault and continue', async () => {
            const probe = new TestProbe(system);
            const parent = system.spawn('parent', ParentActor, { strategy: SupervisionStrategy.Resume, probe: probe.ref, childConstructor: ChildActor });

            await probe.expectMessage('parent:preStart');
            await probe.expectMessage('child:preStart');

            parent.tell('tell-child', 'error');
            parent.tell('tell-child', 'ping', probe.ref);

            await probe.expectMessage('pong');
            await probe.expectNoMessage(100); // No lifecycle hooks
        });

        test('Escalate strategy should escalate the failure to the parent', async () => {
            class GrandparentActor extends Actor<any> implements Supervisor {
                strategy = SupervisionStrategy.Restart;
                constructor(private props: { probe: ActorRef<string> }) { super(props); }
                preStart() {
                    this.context.spawn('parent', ParentActor, {
                        strategy: SupervisionStrategy.Escalate,
                        probe: this.props.probe,
                        childConstructor: ChildActor
                    });
                }
            }

            const probe = new TestProbe(system);
            const grandparent = system.spawn('grandparent', GrandparentActor, { probe: probe.ref });
            
            await probe.expectMessage('parent:preStart');
            await probe.expectMessage('child:preStart');

            grandparent.tell({ type: 'tell-child', target: 'parent', message: 'error' }, ActorRef.noSender);

            // Escalation causes parent to fail, which is then restarted by grandparent
            await probe.expectMessage('child:postStop'); // Child stops as parent is restarting
            await probe.expectMessage('parent:preRestart');
            await probe.expectMessage('parent:postRestart');
            await probe.expectMessage('parent:preStart');
            await probe.expectMessage('child:preStart'); // New child is started
        });
    });
});
