package netmap

import (
	"fmt"

	"github.com/nspcc-dev/neo-go/pkg/vm/stackitem"
	"github.com/nspcc-dev/neofs-node/pkg/morph/client"
)

// ConfigArgs groups the arguments
// of get config value test invoke call.
type ConfigArgs struct {
	key []byte
}

// ConfigValues groups the stack parameters
// returned by get config test invoke.
type ConfigValues struct {
	val interface{}
}

// SetKey sets binary key to configuration parameter.
func (c *ConfigArgs) SetKey(v []byte) {
	c.key = v
}

// Value returns configuration value.
func (c ConfigValues) Value() interface{} {
	return c.val
}

// Config performs the test invoke of get config value
// method of NeoFS Netmap contract.
func (c *Client) Config(args ConfigArgs, assert func(stackitem.Item) (interface{}, error)) (*ConfigValues, error) {
	items, err := c.client.TestInvoke(
		c.configMethod,
		args.key,
	)
	if err != nil {
		return nil, fmt.Errorf("could not perform test invocation (%s): %w",
			c.configMethod, err)
	}

	if ln := len(items); ln != 1 {
		return nil, fmt.Errorf("unexpected stack item count (%s): %d",
			c.configMethod, ln)
	}

	val, err := assert(items[0])
	if err != nil {
		return nil, fmt.Errorf("value type assertion failed: %w", err)
	}

	return &ConfigValues{
		val: val,
	}, nil
}

// SetConfig invokes `setConfig` method of NeoFS Netmap contract.
func (c *Client) SetConfig(id, key []byte, value interface{}) error {
	return c.client.Invoke(c.setConfigMethod, id, key, value)
}

func IntegerAssert(item stackitem.Item) (interface{}, error) {
	return client.IntFromStackItem(item)
}

func StringAssert(item stackitem.Item) (interface{}, error) {
	return client.StringFromStackItem(item)
}

// ListConfigArgs groups the arguments
// of config listing test invoke call.
type ListConfigArgs struct {
}

// ConfigValues groups the stack parameters
// returned by config listing test invoke.
type ListConfigValues struct {
	rs []stackitem.Item
}

// IterateRecords iterates over all config records and passes them to f.
//
// Returns f's errors directly.
func (x ListConfigValues) IterateRecords(f func(key, value []byte) error) error {
	for i := range x.rs {
		fields, err := client.ArrayFromStackItem(x.rs[i])
		if err != nil {
			return fmt.Errorf("record fields: %w", err)
		}

		if ln := len(fields); ln != 2 {
			return fmt.Errorf("unexpected record fields number: %d", ln)
		}

		k, err := client.BytesFromStackItem(fields[0])
		if err != nil {
			return fmt.Errorf("record key: %w", err)
		}

		v, err := client.BytesFromStackItem(fields[1])
		if err != nil {
			return fmt.Errorf("record value: %w", err)
		}

		if err := f(k, v); err != nil {
			return err
		}
	}

	return nil
}

// ListConfig performs the test invoke of config listing method of NeoFS Netmap contract.
func (c *Client) ListConfig(args ListConfigArgs) (*ListConfigValues, error) {
	items, err := c.client.TestInvoke(
		c.configListMethod,
	)
	if err != nil {
		return nil, fmt.Errorf("could not perform test invocation (%s): %w",
			c.configListMethod, err)
	}

	if ln := len(items); ln != 1 {
		return nil, fmt.Errorf("unexpected stack item count (%s): %d",
			c.configListMethod, ln)
	}

	arr, err := client.ArrayFromStackItem(items[0])
	if err != nil {
		return nil, fmt.Errorf("record list (%s): %w",
			c.configListMethod, err)
	}

	return &ListConfigValues{
		rs: arr,
	}, nil
}