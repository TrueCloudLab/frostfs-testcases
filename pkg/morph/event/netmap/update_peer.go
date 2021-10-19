package netmap

import (
	"crypto/elliptic"
	"fmt"

	"github.com/nspcc-dev/neo-go/pkg/crypto/keys"
	"github.com/nspcc-dev/neo-go/pkg/network/payload"
	"github.com/nspcc-dev/neo-go/pkg/vm/stackitem"
	"github.com/nspcc-dev/neofs-api-go/pkg/netmap"
	v2netmap "github.com/nspcc-dev/neofs-api-go/v2/netmap"
	"github.com/nspcc-dev/neofs-node/pkg/morph/client"
	"github.com/nspcc-dev/neofs-node/pkg/morph/event"
)

type UpdatePeer struct {
	publicKey *keys.PublicKey
	status    netmap.NodeState

	// For notary notifications only.
	// Contains raw transactions of notary request.
	notaryRequest *payload.P2PNotaryRequest
}

// MorphEvent implements Neo:Morph Event interface.
func (UpdatePeer) MorphEvent() {}

func (s UpdatePeer) Status() netmap.NodeState {
	return s.status
}

func (s UpdatePeer) PublicKey() *keys.PublicKey {
	return s.publicKey
}

// NotaryRequest returns raw notary request if notification
// was received via notary service. Otherwise, returns nil.
func (s UpdatePeer) NotaryRequest() *payload.P2PNotaryRequest {
	return s.notaryRequest
}

const expectedItemNumUpdatePeer = 2

func ParseUpdatePeer(prms []stackitem.Item) (event.Event, error) {
	var (
		ev  UpdatePeer
		err error
	)

	if ln := len(prms); ln != expectedItemNumUpdatePeer {
		return nil, event.WrongNumberOfParameters(expectedItemNumUpdatePeer, ln)
	}

	// parse public key
	key, err := client.BytesFromStackItem(prms[1])
	if err != nil {
		return nil, fmt.Errorf("could not get public key: %w", err)
	}

	ev.publicKey, err = keys.NewPublicKeyFromBytes(key, elliptic.P256())
	if err != nil {
		return nil, fmt.Errorf("could not parse public key: %w", err)
	}

	// parse node status
	st, err := client.IntFromStackItem(prms[0])
	if err != nil {
		return nil, fmt.Errorf("could not get node status: %w", err)
	}

	ev.status = netmap.NodeStateFromV2(v2netmap.NodeState(st))

	return ev, nil
}