# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: consensus_data.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x14\x63onsensus_data.proto\x12\x0esawtooth_ddpoa\"\x7f\n\rConsensusData\x12\x11\n\ttimestamp\x18\x01 \x01(\r\x12\r\n\x05\x65poch\x18\x02 \x01(\r\x12\x12\n\nwitnessIdx\x18\x03 \x01(\r\x12\x12\n\ncandidates\x18\x04 \x03(\t\x12\x11\n\tconsensus\x18\x05 \x01(\t\x12\x11\n\tnum_slots\x18\x06 \x01(\rb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'consensus_data_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _CONSENSUSDATA._serialized_start=40
  _CONSENSUSDATA._serialized_end=167
# @@protoc_insertion_point(module_scope)