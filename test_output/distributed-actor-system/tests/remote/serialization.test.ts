import { describe, it, expect } from 'bun:test';
import { Serializer } from '../../src/remote/serialization';
import { ActorAddress } from '../../src/types/actor.types';

describe('Serializer', () => {
    const serializer = new Serializer();

    const simpleObject = {
        message: 'hello',
        count: 42,
        active: true,
        data: null,
    };

    const complexObject = {
        id: 'uuid-123',
        payload: {
            items: [1, 'two', { three: 3 }],
            metadata: {
                timestamp: Date.now(),
            },
        },
    };

    const actorAddress = new ActorAddress(
        'my-system',
        '/user/my-actor',
        'local',
        '127.0.0.1',
        8080,
    );

    const plainObjectShapedAsAddress = {
        protocol: 'local',
        systemName: 'my-system',
        host: '127.0.0.1',
        port: 8080,
        path: '/user/my-actor',
    };

    describe('serialize', () => {
        it('should serialize a simple plain object into a Buffer', () => {
            const buffer = serializer.serialize(simpleObject);
            expect(buffer).toBeInstanceOf(Buffer);
            expect(buffer.toString('utf-8')).toEqual(JSON.stringify(simpleObject));
        });

        it('should serialize a complex nested object into a Buffer', () => {
            const buffer = serializer.serialize(complexObject);
            expect(buffer).toBeInstanceOf(Buffer);
            expect(JSON.parse(buffer.toString('utf-8'))).toEqual(complexObject);
        });

        it('should serialize an ActorAddress instance into a plain object representation', () => {
            const buffer = serializer.serialize(actorAddress);
            expect(buffer).toBeInstanceOf(Buffer);
            const deserialized = JSON.parse(buffer.toString('utf-8'));
            expect(deserialized).toEqual(plainObjectShapedAsAddress);
        });

        it('should throw an error when serializing an object with circular references', () => {
            const circular: any = { name: 'circular' };
            circular.self = circular;
            expect(() => serializer.serialize(circular)).toThrow();
        });

        it('should handle an empty object', () => {
            const buffer = serializer.serialize({});
            expect(buffer).toBeInstanceOf(Buffer);
            expect(buffer.toString('utf-8')).toBe('{}');
        });
    });

    describe('deserialize', () => {
        it('should deserialize a buffer into a simple object', () => {
            const buffer = Buffer.from(JSON.stringify(simpleObject));
            const result = serializer.deserialize(buffer);
            expect(result).toEqual(simpleObject);
        });

        it('should deserialize a buffer into a complex nested object', () => {
            const buffer = Buffer.from(JSON.stringify(complexObject));
            const result = serializer.deserialize(buffer);
            expect(result).toEqual(complexObject);
        });

        it('should rehydrate an object with ActorAddress shape into an ActorAddress instance', () => {
            const buffer = Buffer.from(JSON.stringify(plainObjectShapedAsAddress));
            const result = serializer.deserialize(buffer);
            expect(result).toBeInstanceOf(ActorAddress);
            expect(result).toEqual(actorAddress);
        });

        it('should not rehydrate an object that only partially resembles an ActorAddress', () => {
            const partialAddress = {
                systemName: 'my-system',
                path: '/user/my-actor',
            };
            const buffer = Buffer.from(JSON.stringify(partialAddress));
            const result = serializer.deserialize(buffer);
            expect(result).not.toBeInstanceOf(ActorAddress);
            expect(result).toEqual(partialAddress);
        });

        it('should throw an error for a malformed JSON buffer', () => {
            const malformedBuffer = Buffer.from('{ "key": "value", }');
            expect(() => serializer.deserialize(malformedBuffer)).toThrow();
        });

        it('should throw an error for an empty buffer', () => {
            const emptyBuffer = Buffer.alloc(0);
            expect(() => serializer.deserialize(emptyBuffer)).toThrow();
        });

        it('should handle buffers representing non-object JSON values', () => {
            expect(serializer.deserialize(Buffer.from('123'))).toBe(123);
            expect(serializer.deserialize(Buffer.from('"test"'))).toBe('test');
            expect(serializer.deserialize(Buffer.from('null'))).toBeNull();
            expect(serializer.deserialize(Buffer.from('[]'))).toEqual([]);
        });
    });

    describe('Round-trip', () => {
        it('should correctly serialize and deserialize a simple object', () => {
            const buffer = serializer.serialize(simpleObject);
            const deserialized = serializer.deserialize(buffer);
            expect(deserialized).toEqual(simpleObject);
        });

        it('should correctly serialize and deserialize a complex object', () => {
            const buffer = serializer.serialize(complexObject);
            const deserialized = serializer.deserialize(buffer);
            expect(deserialized).toEqual(complexObject);
        });

        it('should correctly serialize and deserialize an ActorAddress, preserving its type', () => {
            const buffer = serializer.serialize(actorAddress);
            const deserialized = serializer.deserialize(buffer);
            expect(deserialized).toBeInstanceOf(ActorAddress);
            expect(deserialized).toEqual(actorAddress);
            expect((deserialized as ActorAddress).toString()).toEqual(actorAddress.toString());
        });
    });
});
