package types

type Principal struct {
	UserID      int64
	RoleID      int64
	Permissions map[string]struct{}
	Superuser   bool
}

func (p Principal) HasPermission(slug string) bool {
	if p.Superuser {
		return true
	}
	_, ok := p.Permissions[slug]
	return ok
}
