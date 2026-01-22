export class Serializer {
  public serialize(message: any): Buffer {
    const jsonString = JSON.stringify(message);
    return Buffer.from(jsonString);
  }

  public deserialize(data: Buffer): any {
    const jsonString = data.toString();
    return JSON.parse(jsonString);
  }
}
