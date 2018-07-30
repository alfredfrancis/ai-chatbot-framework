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

  getEntity(id) {
    return this.http.get(environment.ikyBackend + `entities/${id}`).toPromise();
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
    return this.http.put(environment.ikyBackend + `entities/${entity._id.$oid}`, entity).toPromise();
  }

  delete_entity(id) {
    return this.http.delete(environment.ikyBackend + `entities/${id}`, {}).toPromise();
  }
}


import {Resolve, Router, CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
@Injectable()
export class EntityResolverService implements Resolve<any>  {

    constructor(private _router: Router,private entityService: EntitiesService) { }

    resolve(route: ActivatedRouteSnapshot): Promise<any> | boolean {
        return new Promise((resolve,reject)=>{
            this.entityService.getEntity(route.params['entity_id']).then(
            (result) => {
              console.log("intent details resolved");
              resolve(result);
            },
            (err)=>{
              new Error("Could'nt get intent details")
            }
          )
        });
    }
}
