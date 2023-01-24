// Code generated by protoc-gen-go-frostfs. DO NOT EDIT.

package tree

import "github.com/TrueCloudLab/frostfs-api-go/v2/util/proto"

// StableSize returns the size of x in protobuf format.
//
// Structures with the same field values have the same binary size.
func (x *KeyValue) StableSize() (size int) {
	size += proto.StringSize(1, x.Key)
	size += proto.BytesSize(2, x.Value)
	return size
}

// StableMarshal marshals x in protobuf binary format with stable field order.
//
// If buffer length is less than x.StableSize(), new buffer is allocated.
//
// Returns any error encountered which did not allow writing the data completely.
// Otherwise, returns the buffer in which the data is written.
//
// Structures with the same field values have the same binary format.
func (x *KeyValue) StableMarshal(buf []byte) []byte {
	if x == nil {
		return []byte{}
	}
	if buf == nil {
		buf = make([]byte, x.StableSize())
	}
	var offset int
	offset += proto.StringMarshal(1, buf[offset:], x.Key)
	offset += proto.BytesMarshal(2, buf[offset:], x.Value)
	return buf
}

// StableSize returns the size of x in protobuf format.
//
// Structures with the same field values have the same binary size.
func (x *LogMove) StableSize() (size int) {
	size += proto.UInt64Size(1, x.ParentId)
	size += proto.BytesSize(2, x.Meta)
	size += proto.UInt64Size(3, x.ChildId)
	return size
}

// StableMarshal marshals x in protobuf binary format with stable field order.
//
// If buffer length is less than x.StableSize(), new buffer is allocated.
//
// Returns any error encountered which did not allow writing the data completely.
// Otherwise, returns the buffer in which the data is written.
//
// Structures with the same field values have the same binary format.
func (x *LogMove) StableMarshal(buf []byte) []byte {
	if x == nil {
		return []byte{}
	}
	if buf == nil {
		buf = make([]byte, x.StableSize())
	}
	var offset int
	offset += proto.UInt64Marshal(1, buf[offset:], x.ParentId)
	offset += proto.BytesMarshal(2, buf[offset:], x.Meta)
	offset += proto.UInt64Marshal(3, buf[offset:], x.ChildId)
	return buf
}

// StableSize returns the size of x in protobuf format.
//
// Structures with the same field values have the same binary size.
func (x *Signature) StableSize() (size int) {
	size += proto.BytesSize(1, x.Key)
	size += proto.BytesSize(2, x.Sign)
	return size
}

// StableMarshal marshals x in protobuf binary format with stable field order.
//
// If buffer length is less than x.StableSize(), new buffer is allocated.
//
// Returns any error encountered which did not allow writing the data completely.
// Otherwise, returns the buffer in which the data is written.
//
// Structures with the same field values have the same binary format.
func (x *Signature) StableMarshal(buf []byte) []byte {
	if x == nil {
		return []byte{}
	}
	if buf == nil {
		buf = make([]byte, x.StableSize())
	}
	var offset int
	offset += proto.BytesMarshal(1, buf[offset:], x.Key)
	offset += proto.BytesMarshal(2, buf[offset:], x.Sign)
	return buf
}