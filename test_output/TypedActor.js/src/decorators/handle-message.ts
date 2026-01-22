export const ACTOR_MESSAGE_HANDLERS = Symbol('__actorMessageHandlers');

export function handle<TMessage>(MessageType: new (...args: any[]) => TMessage): MethodDecorator {
    return function (target: any, propertyKey: string | symbol, descriptor: PropertyDescriptor) {
        let handlers: Map<any, string | symbol>;

        if (!Object.prototype.hasOwnProperty.call(target, ACTOR_MESSAGE_HANDLERS)) {
            const parentHandlers = Object.getPrototypeOf(target)?.[ACTOR_MESSAGE_HANDLERS];
            handlers = new Map<any, string | symbol>(parentHandlers);

            Object.defineProperty(target, ACTOR_MESSAGE_HANDLERS, {
                value: handlers,
                configurable: true,
                writable: false,
                enumerable: false,
            });
        } else {
            handlers = target[ACTOR_MESSAGE_HANDLERS];
        }

        handlers.set(MessageType, propertyKey);

        return descriptor;
    };
}
