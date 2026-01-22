import { describe, test, expect } from 'bun:test';
import { Serializer } from './serialization';

describe('Serializer', () => {
    const serializer = new Serializer();

    describe('serialize', () => {
        test('should serialize a simple JSON object into a Buffer', () => {
            const obj = { name: 'TypedActor', version: 1 };
            const expectedBuffer = Buffer.from(JSON.stringify(obj));
            const result = serializer.serialize(obj);
            expect(result).toBeInstanceOf(Buffer);
            expect(result).toEqual(expectedBuffer);
        });

        test('should serialize a primitive string into a Buffer', () => {
            const str = 'hello world';
            const expectedBuffer = Buffer.from(JSON.stringify(str));
            const result = serializer.serialize(str);
            expect(result).toEqual(expectedBuffer);
        });

        test('should serialize a primitive number into a Buffer', () => {
            const num = 12345.67;
            const expectedBuffer = Buffer.from(JSON.stringify(num));
            const result = serializer.serialize(num);
            expect(result).toEqual(expectedBuffer);
        });

        test('should serialize a primitive boolean (true) into a Buffer', () => {
            const bool = true;
            const expectedBuffer = Buffer.from(JSON.stringify(bool));
            const result = serializer.serialize(bool);
            expect(result).toEqual(expectedBuffer);
        });

        test('should serialize null into a Buffer', () => {
            const val = null;
            const expectedBuffer = Buffer.from(JSON.stringify(val));
            const result = serializer.serialize(val);
            expect(result).toEqual(expectedBuffer);
        });

        test('should serialize an array of mixed types into a Buffer', () => {
            const arr = [1, 'two', { three: 3 }, null, true];
            const expectedBuffer = Buffer.from(JSON.stringify(arr));
            const result = serializer.serialize(arr);
            expect(result).toEqual(expectedBuffer);
        });

        test('should serialize a nested object into a Buffer', () => {
            const nestedObj = {
                level1: {
                    value: 'a',
                    level2: {
                        value: 'b',
                        items: [1, 2, 3],
                    },
                },
            };
            const expectedBuffer = Buffer.from(JSON.stringify(nestedObj));
            const result = serializer.serialize(nestedObj);
            expect(result).toEqual(expectedBuffer);
        });

        test('should handle an empty object', () => {
            const obj = {};
            const expectedBuffer = Buffer.from(JSON.stringify(obj));
            const result = serializer.serialize(obj);
            expect(result).toEqual(expectedBuffer);
        });

        test('should handle an empty array', () => {
            const arr = [];
            const expectedBuffer = Buffer.from(JSON.stringify(arr));
            const result = serializer.serialize(arr);
            expect(result).toEqual(expectedBuffer);
        });

        test('should omit undefined properties from objects during serialization', () => {
            const obj = { a: 1, b: undefined, c: 3 };
            const expectedObj = { a: 1, c: 3 };
            const expectedBuffer = Buffer.from(JSON.stringify(expectedObj));
            const result = serializer.serialize(obj);
            expect(result).toEqual(expectedBuffer);
        });

        test('should throw a TypeError for circular references', () => {
            const circularObj: any = { a: 1 };
            circularObj.b = circularObj;
            expect(() => serializer.serialize(circularObj)).toThrow(TypeError);
        });

        test('should throw an error when serializing a standalone undefined value', () => {
            expect(() => serializer.serialize(undefined)).toThrow();
        });

        test('should throw a TypeError when serializing a BigInt', () => {
            const bigIntValue = BigInt(9007199254740991);
            expect(() => serializer.serialize(bigIntValue)).toThrow(TypeError);
        });
    });

    describe('deserialize', () => {
        test('should deserialize a Buffer into a simple JSON object', () => {
            const obj = { name: 'TypedActor', version: 1 };
            const buffer = Buffer.from(JSON.stringify(obj));
            const result = serializer.deserialize(buffer);
            expect(result).toEqual(obj);
        });

        test('should deserialize a Buffer into a primitive string', () => {
            const str = 'hello world';
            const buffer = Buffer.from(JSON.stringify(str));
            const result = serializer.deserialize(buffer);
            expect(result).toBe(str);
        });

        test('should deserialize a Buffer into a primitive number', () => {
            const num = 123.45;
            const buffer = Buffer.from(JSON.stringify(num));
            const result = serializer.deserialize(buffer);
            expect(result).toBe(num);
        });

        test('should deserialize a Buffer into a primitive boolean', () => {
            const bool = false;
            const buffer = Buffer.from(JSON.stringify(bool));
            const result = serializer.deserialize(buffer);
            expect(result).toBe(bool);
        });

        test('should deserialize a Buffer into null', () => {
            const val = null;
            const buffer = Buffer.from(JSON.stringify(val));
            const result = serializer.deserialize(buffer);
            expect(result).toBeNull();
        });

        test('should deserialize a Buffer into a nested object', () => {
            const nestedObj = {
                level1: {
                    value: 'a',
                    level2: {
                        value: 'b',
                        items: [1, 2, 3],
                    },
                },
            };
            const buffer = Buffer.from(JSON.stringify(nestedObj));
            const result = serializer.deserialize(buffer);
            expect(result).toEqual(nestedObj);
        });

        test('should throw a SyntaxError for a malformed JSON Buffer', () => {
            const malformedBuffer = Buffer.from('{ "key": "value", }');
            expect(() => serializer.deserialize(malformedBuffer)).toThrow(SyntaxError);
        });

        test('should throw a SyntaxError for an incomplete JSON Buffer', () => {
            const incompleteBuffer = Buffer.from('{ "key": "value"');
            expect(() => serializer.deserialize(incompleteBuffer)).toThrow(SyntaxError);
        });

        test('should throw a SyntaxError for an empty Buffer', () => {
            const emptyBuffer = Buffer.from('');
            expect(() => serializer.deserialize(emptyBuffer)).toThrow(SyntaxError);
        });
    });

    describe('round-trip serialization', () => {
        test('should correctly serialize and deserialize a complex object', () => {
            const originalObject = {
                id: '123-abc',
                timestamp: new Date().toISOString(),
                active: true,
                count: 99,
                metadata: {
                    source: 'test',
                    correlationId: 'xyz-456',
                },
                tags: ['a', 'b', 'c'],
                data: [
                    { item: 1, value: null },
                    { item: 2, value: 'test' },
                ],
            };

            const serialized = serializer.serialize(originalObject);
            const deserialized = serializer.deserialize(serialized);

            expect(deserialized).toEqual(originalObject);
        });

        test('should correctly serialize and deserialize a simple array', () => {
            const originalArray = [1, 'test', true, null, { key: 'value' }];
            const serialized = serializer.serialize(originalArray);
            const deserialized = serializer.deserialize(serialized);
            expect(deserialized).toEqual(originalArray);
        });

        test('should correctly serialize and deserialize a string value', () => {
            const originalString = "This is a test string with special characters: \" ' / &";
            const serialized = serializer.serialize(originalString);
            const deserialized = serializer.deserialize(serialized);
            expect(deserialized).toBe(originalString);
        });

        test('should correctly serialize and deserialize a number value', () => {
            const originalNumber = -12345.6789;
            const serialized = serializer.serialize(originalNumber);
            const deserialized = serializer.deserialize(serialized);
            expect(deserialized).toBe(originalNumber);
        });

        test('should correctly serialize and deserialize a null value', () => {
            const originalValue = null;
            const serialized = serializer.serialize(originalValue);
            const deserialized = serializer.deserialize(serialized);
            expect(deserialized).toBeNull();
        });
    });
});
