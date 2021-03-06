import copy

from rpython.rlib import jit
from rpython.rlib.objectmodel import compute_unique_id, compute_identity_hash

from topaz.mapdict import MapTransitionCache
from topaz.module import ClassDef, check_frozen
from topaz.scope import StaticScope


class ObjectMetaclass(type):
    def __new__(cls, name, bases, attrs):
        new_cls = super(ObjectMetaclass, cls).__new__(cls, name, bases, attrs)
        if "classdef" in attrs:
            attrs["classdef"].cls = new_cls
        return new_cls


class W_Root(object):
    _attrs_ = []
    __metaclass__ = ObjectMetaclass

    def __deepcopy__(self, memo):
        obj = object.__new__(self.__class__)
        memo[id(self)] = obj
        return obj


class W_BaseObject(W_Root):
    _attrs_ = []

    classdef = ClassDef("BasicObject", filepath=__file__)

    def getclass(self, space):
        return space.getclassobject(self.classdef)

    def is_kind_of(self, space, w_cls):
        return w_cls.is_ancestor_of(self.getclass(space))

    def attach_method(self, space, name, func):
        w_cls = space.getsingletonclass(self)
        w_cls.define_method(space, name, func)

    def is_true(self, space):
        return True

    def find_const(self, space, name):
        raise space.error(space.w_TypeError,
            "%s is not a class/module" % space.str_w(space.send(self, "inspect"))
        )
    find_included_const = find_local_const = find_const

    @classdef.method("initialize")
    def method_initialize(self):
        return self

    @classdef.method("__id__")
    def method___id__(self, space):
        return space.newint(compute_unique_id(self))

    @classdef.method("method_missing")
    def method_method_missing(self, space, w_name, args_w):
        name = space.symbol_w(w_name)
        class_name = space.str_w(space.send(self.getclass(space), "to_s"))
        raise space.error(space.w_NoMethodError,
            "undefined method `%s' for %s" % (name, class_name)
        )

    @classdef.method("==")
    @classdef.method("equal?")
    def method_eq(self, space, w_other):
        return space.newbool(self is w_other)

    @classdef.method("!")
    def method_not(self, space):
        return space.newbool(not space.is_true(self))

    @classdef.method("!=")
    def method_ne(self, space, w_other):
        return space.newbool(
            not space.is_true(space.send(self, "==", [w_other]))
        )

    @classdef.method("__send__", method="str")
    def method_send(self, space, method, args_w, block):
        return space.send(self, method, args_w, block)

    @classdef.method("instance_eval", string="str", filename="str")
    def method_instance_eval(self, space, string=None, filename=None, w_lineno=None, block=None):
        if string is not None:
            if filename is None:
                filename = "instance_eval"
            if w_lineno is not None:
                lineno = space.int_w(w_lineno)
            else:
                lineno = 1
            return space.execute(string, self, StaticScope(space.getclass(self), None), filename, lineno)
        else:
            return space.invoke_block(block.copy(space, w_self=self), [])

    @classdef.method("singleton_method_removed")
    def method_singleton_method_removed(self, space, w_name):
        return space.w_nil

    @classdef.method("singleton_method_added")
    def method_singleton_method_added(self, space, w_name):
        return space.w_nil

    @classdef.method("singleton_method_undefined")
    def method_singleton_method_undefined(self, space, w_name):
        return space.w_nil

    @classdef.method("instance_exec")
    def method_instance_exec(self, space, args_w, block):
        if block is None:
            raise space.error(space.w_LocalJumpError, "no block given")
        return space.invoke_block(
            block.copy(
                space,
                w_self=self,
                lexical_scope=StaticScope(space.getsingletonclass(self), block.lexical_scope)
            ),
            args_w
        )


class W_RootObject(W_BaseObject):
    _attrs_ = []

    classdef = ClassDef("Object", W_BaseObject.classdef, filepath=__file__)

    @classdef.setup_class
    def setup_class(cls, space, w_cls):
        space.w_top_self = W_Object(space, w_cls)

    @classdef.method("object_id")
    def method_object_id(self, space):
        return space.send(self, "__id__")

    @classdef.method("singleton_class")
    def method_singleton_class(self, space):
        return space.getsingletonclass(self)

    @classdef.method("extend")
    def method_extend(self, space, w_mod):
        if not space.is_kind_of(w_mod, space.w_module) or space.is_kind_of(w_mod, space.w_class):
            if space.is_kind_of(w_mod, space.w_class):
                name = "Class"
            else:
                name = space.obj_to_s(space.getclass(w_mod))
            raise space.error(
                space.w_TypeError,
                "wrong argument type %s (expected Module)" % name
            )
        space.send(w_mod, "extend_object", [self])
        space.send(w_mod, "extended", [self])

    @classdef.method("inspect")
    def method_inspect(self, space):
        return space.send(self, "to_s")

    @classdef.method("to_s")
    def method_to_s(self, space):
        return space.newstr_fromstr(space.any_to_s(self))

    @classdef.method("===")
    def method_eqeqeq(self, space, w_other):
        if self is w_other:
            return space.w_true
        return space.send(self, "==", [w_other])

    @classdef.method("send")
    def method_send(self, space, args_w, block):
        return space.send(self, "__send__", args_w, block)

    @classdef.method("nil?")
    def method_nilp(self, space):
        return space.w_false

    @classdef.method("hash")
    def method_hash(self, space):
        return space.newint(compute_identity_hash(self))

    @classdef.method("instance_variable_get", name="str")
    def method_instance_variable_get(self, space, name):
        return space.find_instance_var(self, name)

    @classdef.method("instance_variable_set", name="str")
    @check_frozen()
    def method_instance_variable_set(self, space, name, w_value):
        space.set_instance_var(self, name, w_value)
        return w_value

    @classdef.method("method")
    def method_method(self, space, w_sym):
        return space.send(
            space.send(space.getclass(self), "instance_method", [w_sym]),
            "bind",
            [self]
        )

    @classdef.method("tap")
    def method_tap(self, space, block):
        if block is not None:
            space.invoke_block(block, [self])
        else:
            raise space.error(space.w_LocalJumpError, "no block given")
        return self


class W_Object(W_RootObject):
    _attrs_ = ["map", "storage"]

    def __init__(self, space, klass=None):
        if klass is None:
            klass = space.getclassfor(self.__class__)
        self.map = space.fromcache(MapTransitionCache).get_class_node(klass)
        self.storage = None

    def __deepcopy__(self, memo):
        obj = super(W_Object, self).__deepcopy__(memo)
        obj.map = copy.deepcopy(self.map, memo)
        obj.storage = copy.deepcopy(self.storage, memo)
        return obj

    def getclass(self, space):
        return jit.promote(self.map).get_class()

    def getsingletonclass(self, space):
        w_cls = jit.promote(self.map).get_class()
        if w_cls.is_singleton:
            return w_cls
        w_cls = space.newclass(w_cls.name, w_cls, is_singleton=True, attached=self)
        self.map = self.map.change_class(space, w_cls)
        return w_cls

    def copy_singletonclass(self, space, w_other):
        w_cls = jit.promote(self.map).get_class()
        assert not w_cls.is_singleton
        w_copy = space.newclass(w_cls.name, w_cls, is_singleton=True, attached=self)
        w_copy.methods_w.update(w_other.methods_w)
        w_copy.constants_w.update(w_other.constants_w)
        w_copy.included_modules = w_copy.included_modules + w_other.included_modules
        w_copy.mutated()

        self.map = self.map.change_class(space, w_copy)
        return w_cls

    def find_instance_var(self, space, name):
        idx = jit.promote(self.map).find_attr(space, name)
        if idx == -1:
            return None
        return self.storage[idx]

    def set_instance_var(self, space, name, w_value):
        idx = jit.promote(self.map).find_set_attr(space, name)
        if idx == -1:
            idx = self.map.add_attr(space, self, name)
        self.storage[idx] = w_value

    def copy_instance_vars(self, space, w_other):
        assert isinstance(w_other, W_Object)
        w_other.map.copy_attrs(space, w_other, self)

    def get_flag(self, space, name):
        idx = jit.promote(self.map).find_flag(space, name)
        if idx == -1:
            return space.w_false
        return self.storage[idx]

    def set_flag(self, space, name):
        idx = jit.promote(self.map).find_flag(space, name)
        if idx == -1:
            self.map.add_flag(space, self, name)
        else:
            self.storage[idx] = space.w_true

    def unset_flag(self, space, name):
        idx = jit.promote(self.map).find_flag(space, name)
        if idx != -1:
            # Flags are by default unset, no need to add if unsetting
            self.storage[idx] = space.w_false
