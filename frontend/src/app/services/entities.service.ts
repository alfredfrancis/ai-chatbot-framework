import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
@Injectable()
export class EntitiesService {
  constructor(public http: HttpClient) {
  }

  getEntities() {
    return this.http.get(environment.ikyBackend + 'entities/').toPromise();
  }

  getEntity(name) {
    return this.http.get(environment.ikyBackend + `entities/${name}`).toPromise();
  }

  saveEntity(entity) {
    if (entity._id) {
      return this.update_entity(entity);
    } else {
      delete entity._id;
      return this.create_entity(entity);
    }
  }

  create_entity(entity) {
    return this.http.post(environment.ikyBackend + `entities/`, entity).toPromise();
  }

  update_entity(entity) {
    return this.http.put(environment.ikyBackend + `entities/${entity._id}`, entity).toPromise();
  }

  delete_entity(name) {
    return this.http.delete(environment.ikyBackend + `entities/${name}`, {}).toPromise();
  }
}

