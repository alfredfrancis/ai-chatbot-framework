import { Injectable } from '@angular/core';
import {Resolve, Router, CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import {IntentService  } from './intent.service';

@Injectable()
export class IntentResolverService implements Resolve<any>  {

    constructor(private intentService: IntentService, private _router: Router) { }
    
    resolve(route: ActivatedRouteSnapshot): Promise<any> | boolean {
        return new Promise((resolve,reject)=>{
            this.intentService.getIntent(route.params['intent_id']).then(
            (result) => {
                console.log("intent details resolved")
              resolve(result)
            },
            (err)=>{
              new Error("Could'nt get intent details")
            }
          )
        });
    }
}